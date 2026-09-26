package space.tokenpay.id

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import kotlinx.coroutines.CompletableDeferred
import space.tokenpay.id.ui.WidgetActivity
import java.util.UUID

/**
 * Programmatic entry point for presenting the widget without Compose.
 *
 * Usage:
 * ```
 * lifecycleScope.launch {
 *   val result = TpidWidget.present(activity)
 *   handle(result)
 * }
 * ```
 */
object TpidWidget {
    private val pending = mutableMapOf<String, CompletableDeferred<TpidResult>>()

    /**
     * Present the widget on top of [activity] and suspend until the user completes or dismisses it.
     */
    suspend fun present(
        activity: Activity,
        extraPrefillEmail: String? = null,
    ): TpidResult {
        val state = TpidAuth.requireState()
        val sessionId = UUID.randomUUID().toString()
        val deferred = CompletableDeferred<TpidResult>()
        pending[sessionId] = deferred

        state.telemetry.newSession(sessionId)
        state.telemetry.track("widget.opened")

        val intent = Intent(activity, WidgetActivity::class.java).apply {
            putExtra(EXTRA_SESSION_ID, sessionId)
            if (extraPrefillEmail != null) putExtra(EXTRA_PREFILL_EMAIL, extraPrefillEmail)
        }
        activity.startActivity(intent)
        return deferred.await()
    }

    internal fun deliver(sessionId: String, result: TpidResult) {
        pending.remove(sessionId)?.complete(result)
    }

    internal fun readSession(savedInstanceState: Bundle?, intent: Intent): String? =
        savedInstanceState?.getString(EXTRA_SESSION_ID) ?: intent.getStringExtra(EXTRA_SESSION_ID)

    internal const val EXTRA_SESSION_ID = "space.tokenpay.id.session_id"
    internal const val EXTRA_PREFILL_EMAIL = "space.tokenpay.id.prefill_email"
}
