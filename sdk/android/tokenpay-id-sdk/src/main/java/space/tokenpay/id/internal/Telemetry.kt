package space.tokenpay.id.internal

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.GlobalScope
import kotlinx.coroutines.launch
import kotlinx.serialization.json.*
import space.tokenpay.id.BuildConfig
import java.util.UUID

/**
 * Fire-and-forget funnel telemetry. Events whitelist:
 *  widget.opened, widget.step_shown, widget.step_submit_ok, widget.step_submit_error,
 *  widget.closed_success, widget.closed_cancel, widget.sign_out, widget.error_shown,
 *  widget.device_flow_started, widget.passkey_started, widget.passkey_success, widget.passkey_failed
 *
 * The SDK strips PII from properties client-side before sending. The server also applies
 * its own PII filter.
 */
internal class Telemetry(
    private val api: ApiClient,
    private val clientId: String,
    private val enabled: Boolean,
) {
    @Volatile
    private var sessionId: String = UUID.randomUUID().toString()

    private val forbiddenKeys = setOf(
        "email", "password", "code", "otp", "totp", "token", "secret", "phone",
        "card", "pan", "cvv", "ssn", "passport", "name", "full_name", "address",
        "refresh_token", "access_token", "id_token", "verifier",
    )

    fun newSession(id: String = UUID.randomUUID().toString()) {
        sessionId = id
    }

    fun track(event: String, props: Map<String, Any?> = emptyMap()) {
        if (!enabled) return
        val scrubbed = props
            .filterKeys { it.lowercase() !in forbiddenKeys }
            .mapValues { (_, v) ->
                when (v) {
                    null -> JsonNull
                    is Boolean -> JsonPrimitive(v)
                    is Number -> JsonPrimitive(v)
                    else -> JsonPrimitive(v.toString().take(200))
                }
            }
        val payload = buildJsonObject {
            put("event", event)
            put("client_id", clientId)
            put("session_id", sessionId)
            put("sdk_version", BuildConfig.TPID_SDK_VERSION)
            put("platform", "android")
            put("platform_version", android.os.Build.VERSION.RELEASE)
            put("ts", System.currentTimeMillis())
            put("properties", JsonObject(scrubbed))
        }
        GlobalScope.launch(Dispatchers.IO) {
            runCatching { api.sendTelemetry(payload) }
        }
    }
}
