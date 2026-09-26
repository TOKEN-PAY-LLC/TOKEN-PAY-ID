package space.tokenpay.id.jvm.internal

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.File
import java.io.RandomAccessFile
import java.security.MessageDigest
import java.util.Locale
import java.util.concurrent.TimeUnit

/**
 * 2.6.1 — Smart in-place SDK updater.
 *
 * The updater is the "what actually happens when the user clicks Update"
 * end of the widget's auto-update banner. It is deliberately *honest* about
 * what an embedded SDK can and can't do at runtime on the JVM:
 *
 *  1. Force-refresh the [RemoteConfig] cache by re-fetching
 *     `/api/v1/sdk/config` with a cache-buster. Strings, theme tokens and
 *     feature flags for the running widget therefore apply **live** on the
 *     user's machine the second the download finishes.
 *  2. Download the new SDK tarball (source + fat jar) from the
 *     server-supplied [RemoteConfig.downloadUrl] into the per-user cache
 *     directory `$HOME/.tokenpay-id/sdk/<version>/` and verify its SHA-256
 *     against the `sha256` the server advertises.
 *  3. Bookkeeping: write a marker file `current` containing the version
 *     string so an optional [TpidUpdateBootstrap.install] call at the host
 *     application's startup can prefer the newer cached JAR the next time
 *     the application is launched.
 *
 * `performUpdate` is cancellable, side-effect-free on failure (partial
 * files are deleted) and emits fine-grained [Phase] events so the UI can
 * draw a real progress bar — no fake timeouts.
 */
internal class TpidUpdater(
    private val api: ApiClient,
    private val clientId: String,
    private val httpClient: OkHttpClient = defaultClient(),
    private val cacheRoot: File = defaultCacheRoot(),
) {

    /** Static fact snapshot returned by [checkForUpdate]. */
    internal data class UpdateInfo(
        /** `true` iff the server-recommended version is strictly newer. */
        val hasUpdate: Boolean,
        /** Version we're currently running. */
        val currentVersion: String,
        /** Version the server considers the latest. */
        val latestVersion: String?,
        /** HTTPS URL of the tarball to download; may be empty. */
        val downloadUrl: String,
        /** Expected SHA-256 of [downloadUrl]; `null` when server omits it. */
        val sha256: String?,
        /** Optional changelog, surfaced as tooltip text in the banner. */
        val updateNotes: String,
    )

    /** Fine-grained updater state for the UI. */
    internal sealed class Phase {
        /** Preparing the download; no bytes yet. */
        object Checking : Phase()

        /** Actively downloading; [total] may be `-1` when the server
         *  didn't announce a Content-Length (progress bar stays
         *  indeterminate in that case). */
        data class Downloading(val bytes: Long, val total: Long) : Phase()

        /** SHA-256 check in progress. */
        object Verifying : Phase()

        /** Extracting / moving files into the cache. */
        object Installing : Phase()

        /** Rolling the new [RemoteConfig] into the running widget. */
        object RefreshingConfig : Phase()

        /** Terminal — success. */
        data class Done(val cachedPath: File?, val newConfig: RemoteConfig) : Phase()

        /** Terminal — error; the updater cleaned up any partial files. */
        data class Failed(val reason: String, val cause: Throwable? = null) : Phase()
    }

    /**
     * Query the server without hitting the in-memory cache. Always returns
     * a best-effort [UpdateInfo]; network failures collapse into
     * `hasUpdate=false` so the banner disappears gracefully.
     */
    suspend fun checkForUpdate(): UpdateInfo = withContext(Dispatchers.IO) {
        RemoteConfig.invalidateCache()
        val cfg = RemoteConfig.fetch(api, clientId)
        val current = SdkBuildInfo.version
        val latest = cfg.recommendedSdkVersion
        val newer = cfg.isOlderThan(latest)
        UpdateInfo(
            hasUpdate = newer && cfg.downloadUrl.isNotBlank(),
            currentVersion = current,
            latestVersion = latest,
            downloadUrl = cfg.downloadUrl,
            sha256 = cfg.downloadSha256.takeIf { it.isNotBlank() },
            updateNotes = cfg.updateNotes,
        )
    }

    /**
     * Drive the full update state machine. The caller is expected to be
     * running in a coroutine scope tied to the widget's lifecycle — if the
     * scope is cancelled, the updater aborts cleanly and deletes any
     * partial download.
     *
     * @param onPhase fine-grained progress callback, invoked on whichever
     *                dispatcher the caller used. Re-delivered on the main
     *                thread by the UI layer.
     */
    suspend fun performUpdate(onPhase: (Phase) -> Unit): Phase = withContext(Dispatchers.IO) {
        var partial: File? = null
        try {
            onPhase(Phase.Checking)
            val info = checkForUpdate()
            if (!info.hasUpdate) {
                // Server considers us up-to-date (or provided no URL).
                // Still refresh the config so the live strings/theme are
                // up to date — that's the whole point of "smart update".
                val cfg = RemoteConfig.fetch(api, clientId)
                onPhase(Phase.RefreshingConfig)
                val done = Phase.Done(cachedPath = null, newConfig = cfg)
                onPhase(done)
                return@withContext done
            }

            // Reserve the cache slot.
            val versionDir = File(cacheRoot, info.latestVersion ?: "latest").apply { mkdirs() }
            val fileName = info.downloadUrl.substringAfterLast('/').ifBlank { "sdk.tar.gz" }
            val target = File(versionDir, fileName)
            val tempTarget = File(versionDir, "$fileName.part").also { it.delete() }
            partial = tempTarget

            // --- download ---
            val req = Request.Builder()
                .url(info.downloadUrl)
                .header("User-Agent", SdkBuildInfo.userAgent)
                .build()
            httpClient.newCall(req).execute().use { resp ->
                if (!resp.isSuccessful) {
                    return@withContext fail(onPhase, "download failed: HTTP ${resp.code}", null, partial)
                }
                val total = resp.header("Content-Length")?.toLongOrNull() ?: -1L
                onPhase(Phase.Downloading(0, total))
                val body = resp.body ?: return@withContext fail(onPhase, "empty response body", null, partial)
                val source = body.byteStream()
                tempTarget.outputStream().use { out ->
                    val buf = ByteArray(64 * 1024)
                    var bytes = 0L
                    var lastEmit = 0L
                    while (true) {
                        val n = source.read(buf)
                        if (n <= 0) break
                        out.write(buf, 0, n)
                        bytes += n
                        // Emit at most every 64 KiB or 100 ms so we don't
                        // swamp the Compose recomposer on fast LANs.
                        if (bytes - lastEmit >= 64 * 1024) {
                            onPhase(Phase.Downloading(bytes, total))
                            lastEmit = bytes
                        }
                    }
                    onPhase(Phase.Downloading(bytes, total.takeIf { it > 0 } ?: bytes))
                }
            }

            // --- verify ---
            onPhase(Phase.Verifying)
            val actualSha = sha256Hex(tempTarget)
            if (info.sha256 != null && !info.sha256.equals(actualSha, ignoreCase = true)) {
                return@withContext fail(
                    onPhase,
                    "sha256 mismatch: expected ${info.sha256}, got $actualSha",
                    null,
                    partial,
                )
            }

            // --- install ---
            onPhase(Phase.Installing)
            if (target.exists()) target.delete()
            if (!tempTarget.renameTo(target)) {
                // Cross-FS fallback.
                tempTarget.copyTo(target, overwrite = true)
                tempTarget.delete()
            }
            partial = null
            // Breadcrumb for TpidUpdateBootstrap.
            File(cacheRoot, "current").writeText(
                "${info.latestVersion ?: "unknown"}\t${target.absolutePath}\t${actualSha}\n"
            )

            // --- refresh live config ---
            onPhase(Phase.RefreshingConfig)
            RemoteConfig.invalidateCache()
            val freshCfg = RemoteConfig.fetch(api, clientId)

            val done = Phase.Done(cachedPath = target, newConfig = freshCfg)
            onPhase(done)
            done
        } catch (e: Throwable) {
            fail(onPhase, "update failed: ${e.message ?: e.javaClass.simpleName}", e, partial)
        }
    }

    private fun fail(onPhase: (Phase) -> Unit, reason: String, cause: Throwable?, partial: File?): Phase {
        partial?.runCatching { delete() }
        val f = Phase.Failed(reason, cause)
        onPhase(f)
        return f
    }

    /**
     * Returns the file currently marked as the "latest installed" cached
     * SDK tarball, or `null` if no update has ever been downloaded. Used
     * by [TpidUpdateBootstrap] at host-application start.
     */
    internal fun currentCached(): File? {
        val marker = File(cacheRoot, "current")
        if (!marker.exists()) return null
        val line = marker.readText().lineSequence().firstOrNull().orEmpty()
        val parts = line.split('\t')
        val path = parts.getOrNull(1) ?: return null
        val f = File(path)
        return if (f.exists()) f else null
    }

    companion object {
        private fun defaultCacheRoot(): File {
            val home = System.getProperty("user.home").ifBlank { "." }
            return File(home, ".tokenpay-id/sdk").apply { mkdirs() }
        }

        private fun defaultClient(): OkHttpClient = OkHttpClient.Builder()
            .connectTimeout(10, TimeUnit.SECONDS)
            .readTimeout(60, TimeUnit.SECONDS)
            .callTimeout(3, TimeUnit.MINUTES)
            .build()

        private fun sha256Hex(f: File): String {
            val md = MessageDigest.getInstance("SHA-256")
            RandomAccessFile(f, "r").channel.use { ch ->
                val buf = java.nio.ByteBuffer.allocate(128 * 1024)
                while (ch.position() < ch.size()) {
                    buf.clear()
                    val n = ch.read(buf)
                    if (n <= 0) break
                    buf.flip()
                    md.update(buf)
                }
            }
            return md.digest().joinToString(separator = "") { b -> "%02x".format(b) }
                .lowercase(Locale.ROOT)
        }
    }
}
