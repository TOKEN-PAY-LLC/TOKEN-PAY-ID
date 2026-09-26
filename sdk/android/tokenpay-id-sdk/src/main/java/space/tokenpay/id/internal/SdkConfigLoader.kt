package space.tokenpay.id.internal

import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.contentOrNull
import space.tokenpay.id.TpidConfig

/**
 * Fetches /sdk/config (branding, endpoints, TLS pins) and caches in SecureStorage.
 */
internal class SdkConfigLoader(
    private val api: ApiClient,
    private val storage: SecureStorage,
) {
    /**
     * Refresh SDK config for the given client. Updates TLS pins and cached branding.
     * Returns [TpidConfig.Branding] from the server or null if not provided.
     */
    suspend fun refreshConfig(clientId: String): TpidConfig.Branding? {
        val cfg = api.fetchSdkConfig(clientId)
        storage.putString(SecureStorage.KEY_SDK_CONFIG, cfg.toString())
        storage.putLong(SecureStorage.KEY_SDK_CONFIG_FETCHED, System.currentTimeMillis())

        // Extract TLS pins if present
        val pinsArr = cfg["tls_pinning"]?.jsonObject?.get("pins")?.jsonArray
            ?: cfg["tls_pins"]?.jsonArray
        val pins = pinsArr?.mapNotNull { it.jsonPrimitive.contentOrNull } ?: emptyList()
        if (pins.isNotEmpty()) api.refreshPins(pins)
        else runCatching { api.fetchTlsPins() }.onSuccess(api::refreshPins)

        // Extract branding
        val br = cfg["branding"]?.jsonObject ?: return null
        return TpidConfig.Branding(
            logoUrl = (br["logo_url"] ?: br["logo_uri"] ?: br["app_icon_url"])
                ?.jsonPrimitive?.contentOrNull,
            primaryColor = br["primary_color"]?.jsonPrimitive?.contentOrNull,
            appName = (br["app_name"] ?: br["client_name"])?.jsonPrimitive?.contentOrNull,
            appDomain = (br["app_domain"] ?: br["client_uri"])?.jsonPrimitive?.contentOrNull,
        )
    }

    /** Cached branding from last successful refresh. */
    fun cachedBranding(): TpidConfig.Branding? {
        val raw = storage.getString(SecureStorage.KEY_SDK_CONFIG) ?: return null
        val obj: JsonObject = runCatching { kotlinx.serialization.json.Json.parseToJsonElement(raw).jsonObject }
            .getOrNull() ?: return null
        val br = obj["branding"]?.jsonObject ?: return null
        return TpidConfig.Branding(
            logoUrl = (br["logo_url"] ?: br["logo_uri"] ?: br["app_icon_url"])
                ?.jsonPrimitive?.contentOrNull,
            primaryColor = br["primary_color"]?.jsonPrimitive?.contentOrNull,
            appName = (br["app_name"] ?: br["client_name"])?.jsonPrimitive?.contentOrNull,
            appDomain = (br["app_domain"] ?: br["client_uri"])?.jsonPrimitive?.contentOrNull,
        )
    }
}
