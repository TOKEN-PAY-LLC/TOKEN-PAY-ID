package space.tokenpay.id.internal

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import space.tokenpay.id.BuildConfig
import java.util.concurrent.atomic.AtomicReference

/**
 * Runtime-fetched configuration for the TOKEN PAY ID widget on Android.
 *
 * Integrators don't have to rebuild to pick up new colour tokens, translated
 * strings, or feature-flag toggles we ship from the server. The widget calls
 * `GET /api/v1/sdk/config?client_id=…` once per launch and merges the
 * `remote` section on top of the locally-bundled defaults.
 *
 * Keep the keys in sync with the JVM / Swift variants
 * (`RemoteConfig.kt` and `RemoteConfig.swift`).
 */
internal data class RemoteConfig(
    val themeTokens: Map<String, String> = emptyMap(),
    val stringsOverride: Map<String, Map<String, String>> = emptyMap(),
    val featureFlags: Map<String, Boolean> = emptyMap(),
    val minSdkVersion: String? = null,
    val recommendedSdkVersion: String? = null,
    /**
     * 2.6.0 — URL that the update banner's "Update" pill opens in the
     * system browser. The server populates this from
     * `remote.download_url` in `/sdk/config`; if absent, the widget
     * falls back to the public docs page.
     */
    val downloadUrl: String? = null,
    val updateNotes: String? = null,
    /**
     * 2.6.1 — SHA-256 of the [downloadUrl] tarball (lowercase hex).
     * Verified byte-for-byte by [TpidUpdater] before the cached file is
     * moved into its final slot. `null` means the server didn't advertise
     * one; the updater still succeeds but cannot self-attest.
     */
    val downloadSha256: String? = null,
) {
    companion object {
        /** In-memory cache keyed on `clientId` — one network round-trip per widget launch. */
        private val cache = AtomicReference<Pair<String, RemoteConfig>?>(null)

        /**
         * Fetch the remote config for [clientId]. Never throws — a network or
         * parse failure returns an empty [RemoteConfig] so the widget still
         * works offline with its bundled defaults.
         */
        suspend fun fetch(api: ApiClient, clientId: String): RemoteConfig = withContext(Dispatchers.IO) {
            cache.get()?.let { if (it.first == clientId) return@withContext it.second }
            val parsed = runCatching { parse(api.fetchSdkConfig(clientId)) }.getOrDefault(RemoteConfig())
            cache.set(clientId to parsed)
            parsed
        }

        /**
         * 2.6.1 — Drop the memoised snapshot. [TpidUpdater] calls this
         * before its force-refresh so the next [fetch] goes to the network
         * and the running widget picks up any hot-pushed strings / theme /
         * feature-flag changes in the same frame.
         */
        fun invalidateCache() { cache.set(null) }

        private fun parse(root: JsonObject): RemoteConfig {
            val remote = (root["remote"] as? JsonObject) ?: return RemoteConfig()
            val theme = (remote["theme_tokens"] as? JsonObject)?.mapValues { (_, v) ->
                runCatching { v.jsonPrimitive.contentOrNull.orEmpty() }.getOrDefault("")
            }?.filterValues { it.isNotBlank() } ?: emptyMap()
            val strings: Map<String, Map<String, String>> = (remote["strings_override"] as? JsonObject)
                ?.mapValues { (_, langEntry) ->
                    (langEntry as? JsonObject)?.mapValues { (_, v) ->
                        runCatching { v.jsonPrimitive.contentOrNull.orEmpty() }.getOrDefault("")
                    }?.filterValues { it.isNotBlank() } ?: emptyMap()
                }?.filterValues { it.isNotEmpty() } ?: emptyMap()
            val flags = (remote["feature_flags"] as? JsonObject)?.mapValues { (_, v) ->
                runCatching {
                    v.jsonPrimitive.contentOrNull?.toBooleanStrictOrNull() ?: false
                }.getOrDefault(false)
            } ?: emptyMap()
            val minV = (remote["min_sdk_version"] as? kotlinx.serialization.json.JsonElement)
                ?.jsonPrimitive?.contentOrNull
            val recV = (remote["recommended_sdk_version"] as? kotlinx.serialization.json.JsonElement)
                ?.jsonPrimitive?.contentOrNull
            val dl = (remote["download_url"] as? kotlinx.serialization.json.JsonElement)
                ?.jsonPrimitive?.contentOrNull
            val notes = (remote["update_notes"] as? kotlinx.serialization.json.JsonElement)
                ?.jsonPrimitive?.contentOrNull
            val sha = (remote["download_sha256"] as? kotlinx.serialization.json.JsonElement)
                ?.jsonPrimitive?.contentOrNull
            return RemoteConfig(theme, strings, flags, minV, recV, dl, notes, sha)
        }
    }

    /**
     * Returns true when the running SDK build is older than [other]. A missing
     * [other] yields false, so a server omitting the field never triggers the
     * update banner.
     */
    fun isOlderThan(other: String?): Boolean {
        val otherV = other ?: return false
        return compareSemver(BuildConfig.TPID_SDK_VERSION, otherV) < 0
    }

    private fun compareSemver(a: String, b: String): Int {
        fun norm(v: String) = v.split('-', limit = 2).let { parts ->
            val core = parts[0]
            val pre = parts.getOrNull(1) ?: ""
            val nums = core.split('.').mapNotNull { it.toIntOrNull() }
            Triple(nums, pre.isBlank(), pre)
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
