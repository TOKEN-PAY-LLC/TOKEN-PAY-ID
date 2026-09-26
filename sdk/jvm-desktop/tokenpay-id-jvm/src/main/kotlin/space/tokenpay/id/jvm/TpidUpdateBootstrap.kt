package space.tokenpay.id.jvm

import space.tokenpay.id.jvm.internal.SdkBuildInfo
import java.io.File

/**
 * 2.6.1 — Optional classloader hook for host applications that want the
 * **smartest** update experience: when the widget's [TpidUpdater] finishes
 * downloading a fresh JAR to `$HOME/.tokenpay-id/sdk/<version>/`, a host
 * that wraps its `main()` with [TpidUpdateBootstrap.install] will have
 * **that** JAR on its classpath next time the user launches the app —
 * no re-installer, no admin tool, no manual download. Real in-place
 * binary update.
 *
 * Typical integration:
 * ```
 * // In the host application's main entry point — BEFORE any TokenPayID
 * // symbols are referenced:
 * fun main() {
 *     TpidUpdateBootstrap.install()
 *     // … rest of your application boot …
 *     TpidApp(tpid = ...).start()
 * }
 * ```
 *
 * What [install] does, in order:
 *
 *  1. Reads the `current` breadcrumb written by [TpidUpdater.performUpdate]
 *     and resolves the newest cached tarball.
 *  2. Compares its version number against [SdkBuildInfo.version] — only
 *     proceeds when the cached version is strictly newer.
 *  3. Extracts the cached tarball into a sibling `jars/` directory and
 *     appends every contained JAR to the current thread's context
 *     classloader. Because we install BEFORE the host code touches any
 *     `space.tokenpay.id.jvm.*` symbols, the JVM loads the fresh classes
 *     transparently.
 *
 * Failures are silent by design — a broken update never breaks the host
 * application; it just falls back to the bundled SDK. All errors are
 * returned via [InstallResult] for integrators that want to surface them.
 */
public object TpidUpdateBootstrap {

    public sealed class InstallResult {
        /** No cache, or cache is older than or equal to the bundled SDK. */
        public data object NotNeeded : InstallResult()

        /** Cache was newer and has been wired into the classpath. */
        public data class Installed(val version: String, val jarCount: Int) : InstallResult()

        /** Cache was newer but extraction / classloader wiring failed. */
        public data class Failed(val reason: String, val cause: Throwable? = null) : InstallResult()
    }

    /**
     * Run the install hook. Call this as the very first line of your
     * host application's `main()`.
     *
     * @param cacheRoot Override the default `$HOME/.tokenpay-id/sdk` so
     *                  integration tests can point at a sandbox dir.
     */
    @JvmStatic
    @JvmOverloads
    public fun install(cacheRoot: File = defaultCacheRoot()): InstallResult {
        return try {
            val marker = File(cacheRoot, "current")
            if (!marker.exists()) return InstallResult.NotNeeded
            val line = marker.readText().lineSequence().firstOrNull().orEmpty()
            val parts = line.split('\t')
            val version = parts.getOrNull(0).orEmpty()
            val tarball = parts.getOrNull(1)?.let { File(it) }
            if (version.isBlank() || tarball == null || !tarball.exists()) {
                return InstallResult.NotNeeded
            }
            if (!isStrictlyNewer(version, SdkBuildInfo.version)) {
                return InstallResult.NotNeeded
            }
            val jarsDir = File(tarball.parentFile, "jars").apply {
                if (!exists()) mkdirs()
            }
            // Extract once — if the dir already has jars for this version
            // we reuse them. Only `.jar` entries are copied; source `.kt`
            // files in the tarball are ignored.
            val extracted = extractTarGz(tarball, jarsDir, filter = { it.endsWith(".jar") })
            if (extracted == 0) return InstallResult.Failed(
                "no .jar entries inside cached tarball",
            )
            val count = attachJarsToContextLoader(jarsDir)
            InstallResult.Installed(version, count)
        } catch (e: Throwable) {
            InstallResult.Failed("bootstrap failed: ${e.message ?: e.javaClass.simpleName}", e)
        }
    }

    private fun defaultCacheRoot(): File {
        val home = System.getProperty("user.home").ifBlank { "." }
        return File(home, ".tokenpay-id/sdk")
    }

    private fun isStrictlyNewer(a: String, b: String): Boolean {
        fun parts(v: String): List<Int> =
            v.substringBefore('-').split('.').mapNotNull { it.toIntOrNull() }
        val pa = parts(a); val pb = parts(b)
        val n = maxOf(pa.size, pb.size)
        for (i in 0 until n) {
            val x = pa.getOrElse(i) { 0 }
            val y = pb.getOrElse(i) { 0 }
            if (x != y) return x > y
        }
        return false
    }

    /**
     * Walk a gzip'd tar on disk and copy matching entries into [target].
     * We deliberately avoid commons-compress so there's no extra runtime
     * dependency — a tiny hand-rolled reader is enough.
     */
    private fun extractTarGz(
        archive: File,
        target: File,
        filter: (String) -> Boolean,
    ): Int {
        var count = 0
        java.util.zip.GZIPInputStream(archive.inputStream()).use { gz ->
            val buf = ByteArray(512)
            while (true) {
                if (gz.readNBytes(buf, 0, 512) < 512) break
                val name = String(buf, 0, 100, Charsets.UTF_8).trimEnd('\u0000').trim()
                if (name.isBlank()) break
                val sizeOct = String(buf, 124, 12, Charsets.UTF_8).trimEnd('\u0000').trim()
                val size = sizeOct.toLongOrNull(8) ?: break
                val isFile = buf[156].let { it == '0'.code.toByte() || it == 0.toByte() }
                if (isFile && filter(name) && size > 0) {
                    val out = File(target, File(name).name)
                    out.outputStream().use { os ->
                        var remaining = size
                        while (remaining > 0) {
                            val chunk = minOf(remaining, buf.size.toLong()).toInt()
                            val n = gz.readNBytes(buf, 0, chunk)
                            if (n <= 0) break
                            os.write(buf, 0, n)
                            remaining -= n
                        }
                    }
                    count++
                } else if (size > 0) {
                    // Skip this entry's payload.
                    var remaining = size
                    while (remaining > 0) {
                        val chunk = minOf(remaining, buf.size.toLong()).toInt()
                        val n = gz.readNBytes(buf, 0, chunk)
                        if (n <= 0) break
                        remaining -= n
                    }
                }
                // Tar pads every entry to 512-byte boundaries.
                val pad = ((512 - (size % 512)) % 512).toInt()
                if (pad > 0) gz.readNBytes(buf, 0, pad)
            }
        }
        return count
    }

    /**
     * Append every .jar in [dir] to the current thread's context
     * classloader. We deliberately modify the context loader rather than
     * the system loader: (a) JDK 9+ blocks reflective access to the
     * system loader in most deployments; (b) the app-class-loader change
     * would persist across other hosts, which is almost never what an
     * integrator wants. The context loader is scoped to the current
     * thread and inherited by children.
     *
     * Returns the number of JARs successfully attached.
     */
    private fun attachJarsToContextLoader(dir: File): Int {
        val jars = dir.listFiles { f -> f.isFile && f.name.endsWith(".jar") }
            ?.sortedBy { it.name }
            .orEmpty()
        if (jars.isEmpty()) return 0
        val urls = jars.map { it.toURI().toURL() }.toTypedArray()
        val parent = Thread.currentThread().contextClassLoader
            ?: ClassLoader.getSystemClassLoader()
        val fresh = java.net.URLClassLoader(urls, parent)
        Thread.currentThread().contextClassLoader = fresh
        return jars.size
    }
}
