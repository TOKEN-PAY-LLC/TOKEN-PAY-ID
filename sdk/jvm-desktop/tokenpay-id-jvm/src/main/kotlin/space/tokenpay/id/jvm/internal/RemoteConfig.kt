package space.tokenpay.id.jvm.internal

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import java.util.concurrent.atomic.AtomicReference

/**
 * Runtime-fetched configuration for the TOKEN PAY ID widget.
 *
 * Enterprises using the native SDK can receive UI changes — new colour tokens,
 * translated strings, feature-flag toggles — without rebuilding their app.
 * The SDK asks `GET /api/v1/sdk/config?client_id=…&sdk=jvm&v=<version>` once
 * per widget launch; the server's `remote` section is applied on top of the
 * locally-bundled defaults so updates are additive.
 *
 * Contract (fields under `remote`):
 *
 *  - `theme_tokens`  : map of colour / radius / spacing overrides — applied
 *                      to the Compose `ColorScheme` when rendering the widget.
 *  - `strings_override[<lang>][<key>]` : per-language string overrides — fed
 *                      to [Strings] before the widget renders.
 *  - `feature_flags` : key/bool pairs — used to toggle alt-login methods.
 *  - `min_sdk_version` / `recommended_sdk_version` : the widget shows a
 *                      "please update" banner if the running SDK is older
 *                      than the minimum.
 *
 * Missing fields are simply ignored — the SDK falls back to its defaults.
 */
internal data class RemoteConfig(
    val themeTokens: Map<String, String> = emptyMap(),
    val stringsOverride: Map<String, Map<String, String>> = emptyMap(),
    val featureFlags: Map<String, Boolean> = emptyMap(),
    val minSdkVersion: String? = null,
    val recommendedSdkVersion: String? = null,
    /**
     * Host-facing download URL for [recommendedSdkVersion]. The widget's
     * "Update" button opens this URL in the default browser so the
     * integrator can grab the new tarball without leaving the app.
     * Defaults to an empty string, which the widget interprets as "no
     * download link available, point the user at /sdk".
     */
    val downloadUrl: String = "",
    /** Optional short changelog shown in the update banner's tooltip. */
    val updateNotes: String = "",
    /**
     * 2.6.1 — SHA-256 of the [downloadUrl] tarball, hex-encoded, lowercase.
     * Populated from `remote.download_sha256` (per-platform) in `/sdk/config`
     * and verified byte-for-byte by [TpidUpdater] before the cached file is
     * moved into place. Empty string means "server didn't provide one" —
     * the updater still succeeds in that case but cannot self-attest.
     */
    val downloadSha256: String = "",
    /** Enterprise name from the root `branding` object, if the client is active. */
    val clientName: String? = null,
) {
    companion object {
        /** In-memory cache keyed on `clientId`. One request per widget launch. */
        private val cache = AtomicReference<Pair<String, RemoteConfig>?>(null)

        /**
         * Fetch the remote config for [clientId] via [ApiClient].
         *
         * Never throws — a network failure just returns an empty config so
         * the widget still works offline. A previously-cached value survives
         * for the lifetime of the process.
         */
        suspend fun fetch(apiClient: ApiClient, clientId: String): RemoteConfig = withContext(Dispatchers.IO) {
            cache.get()?.let { if (it.first == clientId) return@withContext it.second }
            val parsed = runCatching { parse(apiClient.fetchSdkConfig(clientId)) }.getOrDefault(RemoteConfig())
            cache.set(clientId to parsed)
            parsed
        }

        /**
         * 2.6.1 — Drop the memoised value. Called by [TpidUpdater] before a
         * forced refresh so the next [fetch] actually hits the network and
         * any `remote.strings_override` / `theme_tokens` edits the operator
         * made take effect in the running widget.
         */
        fun invalidateCache() { cache.set(null) }

        private fun parse(root: JsonObject): RemoteConfig {
            val remote = (root["remote"] as? JsonObject) ?: return RemoteConfig()
            val theme = (remote["theme_tokens"] as? JsonObject)?.mapValues { (_, v) ->
                runCatching { v.jsonPrimitive.content }.getOrDefault("")
            }?.filterValues { it.isNotBlank() } ?: emptyMap()
            val stringsRoot = remote["strings_override"] as? JsonObject
            val strings: Map<String, Map<String, String>> = stringsRoot?.mapValues { (_, langEntry) ->
                (langEntry as? JsonObject)?.mapValues { (_, v) ->
                    runCatching { v.jsonPrimitive.content }.getOrDefault("")
                }?.filterValues { it.isNotBlank() } ?: emptyMap()
            }?.filterValues { it.isNotEmpty() } ?: emptyMap()
            val flags = (remote["feature_flags"] as? JsonObject)?.mapValues { (_, v) ->
                runCatching { v.jsonPrimitive.content.toBooleanStrictOrNull() ?: false }.getOrDefault(false)
            } ?: emptyMap()
            val minV = runCatching { remote["min_sdk_version"]?.jsonPrimitive?.content }.getOrNull()
            val recV = runCatching { remote["recommended_sdk_version"]?.jsonPrimitive?.content }.getOrNull()
            val dlUrl = runCatching { remote["download_url"]?.jsonPrimitive?.content }.getOrNull().orEmpty()
            val notes = runCatching { remote["update_notes"]?.jsonPrimitive?.content }.getOrNull().orEmpty()
            val sha = runCatching { remote["download_sha256"]?.jsonPrimitive?.content }.getOrNull().orEmpty()
            val clientName = ((root["branding"] as? JsonObject)?.get("client_name"))
                ?.let { runCatching { it.jsonPrimitive.content }.getOrNull() }
                ?.takeIf { it.isNotBlank() }
            return RemoteConfig(theme, strings, flags, minV, recV, dlUrl, notes, sha, clientName)
        }
    }

    /**
     * Semver comparison just good enough for the two fields we care about.
     * Pre-release suffixes (`-pre.X`, `-rc.Y`) are treated as *older* than
     * the same version without a suffix, matching user expectations.
     */
    fun isOlderThan(other: String?): Boolean {
        val otherV = other ?: return false
        val self = SdkBuildInfo.version
        return compareSemver(self, otherV) < 0
    }

    private fun compareSemver(a: String, b: String): Int {
        // Split the version into numeric core + optional pre-release suffix.
        // Using positional destructuring here crashed on clean semver like
        // "2.5.0" (single-element list) — see 2.5.0-pre.3 changelog.
        fun norm(v: String): Triple<List<Int>, Boolean, String> {
            val parts = v.split('-', limit = 2)
            val core = parts.getOrNull(0).orEmpty()
            val pre  = parts.getOrNull(1).orEmpty()
            val nums = core.split('.').mapNotNull { it.toIntOrNull() }
            return Triple(nums, pre.isBlank(), pre)
        }
        val (an, ac, ap) = norm(a)
        val (bn, bc, bp) = norm(b)
        val size = maxOf(an.size, bn.size)
        for (i in 0 until size) {
            val av = an.getOrElse(i) { 0 }
            val bv = bn.getOrElse(i) { 0 }
            if (av != bv) return av.compareTo(bv)
        }
        if (ac != bc) return if (ac) 1 else -1 // no-suffix > suffix
        return ap.compareTo(bp)
    }
}

/** Compile-time constants describing this build of the SDK. */
internal object SdkBuildInfo {
    const val version: String = "3.0.1"
    const val platform: String = "jvm"
    const val userAgent: String = "TokenPayID-JVM/$version"
    const val sdkHeader: String = "jvm-desktop/$version"
}
