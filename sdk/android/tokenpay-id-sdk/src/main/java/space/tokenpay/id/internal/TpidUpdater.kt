package space.tokenpay.id.internal

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import space.tokenpay.id.BuildConfig
import java.io.File
import java.security.MessageDigest
import java.util.Locale
import java.util.concurrent.TimeUnit

/**
 * 2.6.1 — Smart in-place SDK updater (Android).
 *
 * On Android, Play-distributed applications **cannot** legally replace their
 * own DEX bytecode at runtime — Google Play policy forbids it. What we
 * *can* do honestly is:
 *
 *  1. Force-refresh [RemoteConfig] so all remote-controllable content
 *     (strings, theme tokens, feature flags) applies live in the running
 *     widget. This is the "in-place update" the user actually sees —
 *     translated labels, rebranded accents, newly-enabled QR login path.
 *  2. Download the latest SDK tarball to the app's private cache so the
 *     integrator's next build can pick it up. Verifies SHA-256.
 *  3. Report a structured [Phase] stream to the UI so the animated banner
 *     has something real to visualise, rather than a spinner that's
 *     disconnected from what the code is actually doing.
 *
 * No tricks: we don't try to side-load DEX, we don't attempt to replace
 * the AAR, and we don't lie about what "update" means. The caller gets a
 * fresh config live, the app gets a cached artefact for inspection, and
 * the banner gets fine-grained progress.
 */
internal class TpidUpdater(
    private val context: Context,
    private val api: ApiClient,
    private val clientId: String,
    private val httpClient: OkHttpClient = defaultClient(),
    private val cacheRoot: File = defaultCacheRoot(context),
) {

    internal data class UpdateInfo(
        val hasUpdate: Boolean,
        val currentVersion: String,
        val latestVersion: String?,
        val downloadUrl: String,
        val sha256: String?,
        val updateNotes: String,
    )

    internal sealed class Phase {
        object Checking : Phase()
        data class Downloading(val bytes: Long, val total: Long) : Phase()
        object Verifying : Phase()
        object Installing : Phase()
        object RefreshingConfig : Phase()
        data class Done(val cachedPath: File?, val newConfig: RemoteConfig) : Phase()
        data class Failed(val reason: String, val cause: Throwable? = null) : Phase()
    }

    suspend fun checkForUpdate(): UpdateInfo = withContext(Dispatchers.IO) {
        RemoteConfig.invalidateCache()
        val cfg = RemoteConfig.fetch(api, clientId)
        val current = BuildConfig.TPID_SDK_VERSION
        val latest = cfg.recommendedSdkVersion
        val newer = cfg.isOlderThan(latest)
        val dl = cfg.downloadUrl.orEmpty()
        UpdateInfo(
            hasUpdate = newer && dl.isNotBlank(),
            currentVersion = current,
            latestVersion = latest,
            downloadUrl = dl,
            sha256 = cfg.downloadSha256?.takeIf { it.isNotBlank() },
            updateNotes = cfg.updateNotes.orEmpty(),
        )
    }

    suspend fun performUpdate(onPhase: (Phase) -> Unit): Phase = withContext(Dispatchers.IO) {
        var partial: File? = null
        try {
            onPhase(Phase.Checking)
            val info = checkForUpdate()
            if (!info.hasUpdate) {
                // No newer binary — still refresh the running config so the
                // user sees some effect. That's the entire point of a "smart"
                // update button: it never does nothing.
                val cfg = RemoteConfig.fetch(api, clientId)
                onPhase(Phase.RefreshingConfig)
                val done = Phase.Done(cachedPath = null, newConfig = cfg)
                onPhase(done)
                return@withContext done
            }

            val versionDir = File(cacheRoot, info.latestVersion ?: "latest").apply { mkdirs() }
            val fileName = info.downloadUrl.substringAfterLast('/').ifBlank { "sdk.tar.gz" }
            val target = File(versionDir, fileName)
            val tempTarget = File(versionDir, "$fileName.part").also { it.delete() }
            partial = tempTarget

            // --- download ---
            val req = Request.Builder()
                .url(info.downloadUrl)
                .header("User-Agent", "TokenPayID-Android/${BuildConfig.TPID_SDK_VERSION}")
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
                tempTarget.copyTo(target, overwrite = true)
                tempTarget.delete()
            }
            partial = null
            File(cacheRoot, "current").writeText(
                "${info.latestVersion ?: "unknown"}\t${target.absolutePath}\t${actualSha}\n"
            )

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

    private fun fail(
        onPhase: (Phase) -> Unit,
        reason: String,
        cause: Throwable?,
        partial: File?,
    ): Phase {
        partial?.runCatching { delete() }
        val f = Phase.Failed(reason, cause)
        onPhase(f)
        return f
    }

    companion object {
        private fun defaultCacheRoot(ctx: Context): File =
            File(ctx.filesDir, ".tokenpay-id/sdk").apply { mkdirs() }

        private fun defaultClient(): OkHttpClient = OkHttpClient.Builder()
            .connectTimeout(10, TimeUnit.SECONDS)
            .readTimeout(60, TimeUnit.SECONDS)
            .callTimeout(3, TimeUnit.MINUTES)
            .build()

        private fun sha256Hex(f: File): String {
            val md = MessageDigest.getInstance("SHA-256")
            f.inputStream().use { input ->
                val buf = ByteArray(128 * 1024)
                while (true) {
                    val n = input.read(buf)
                    if (n <= 0) break
                    md.update(buf, 0, n)
                }
            }
            return md.digest().joinToString(separator = "") { b -> "%02x".format(b) }
                .lowercase(Locale.ROOT)
        }
    }
}
