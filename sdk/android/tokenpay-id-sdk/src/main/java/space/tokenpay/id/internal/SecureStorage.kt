package space.tokenpay.id.internal

import android.content.Context
import android.content.SharedPreferences
import android.util.Log
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import space.tokenpay.id.TpidUser
import java.security.GeneralSecurityException
import java.security.KeyStore

/**
 * Secure persistent storage for tokens, PKCE state, and cached config.
 * Uses [EncryptedSharedPreferences] with hardware-backed [MasterKey] when available.
 *
 * **B2 (2.6.0 — was open since pre.2)**: on OPPO / Xiaomi / Samsung ROMs the
 * `_androidx_security_master_key_` alias survives app uninstall but the
 * backing `SharedPreferences` XML file is deleted. The next install reads a
 * fresh empty file with the stale key and [EncryptedSharedPreferences.create]
 * throws `AEADBadTagException` wrapped in `GeneralSecurityException`. We
 * now detect that, purge the prefs file *and* the Keystore alias, and retry
 * from scratch so the integrator app never crashes with a Tink stack.
 */
internal class SecureStorage(context: Context, clientId: String) {

    private val json = Json { ignoreUnknownKeys = true; encodeDefaults = true }
    private val prefsName = "tpid_${clientId.takeLast(20)}"
    private val fallbackName = "tpid_fallback_${prefsName.takeLast(20)}"
    private val recoveryPrefs: SharedPreferences = context.getSharedPreferences("tpid_recovery_${prefsName.takeLast(20)}", Context.MODE_PRIVATE)
    private val prefs: SharedPreferences = openEncryptedOrRecover(context, prefsName, fallbackName)

    companion object {
        private const val KEY_TOKENS = "tokens.v1"
        private const val KEY_PKCE_VERIFIER = "pkce.verifier"
        private const val KEY_PKCE_STATE = "pkce.state"
        private const val KEY_PKCE_NONCE = "pkce.nonce"
        const val KEY_TLS_PINS = "tls.pins"
        const val KEY_TLS_PINS_FETCHED = "tls.pins.ts"
        const val KEY_SDK_CONFIG = "sdk.config"
        const val KEY_SDK_CONFIG_FETCHED = "sdk.config.ts"
        const val KEY_SESSION_VERSION = "session.version"
        // 2.6.0: account memory
        private const val KEY_LAST_EMAIL = "account.last.email"
        private const val KEY_LAST_NAME = "account.last.name"
        private const val KEY_LAST_AVATAR = "account.last.avatar"
        private const val KEY_LAST_AUTH_AT = "account.last.auth_at"
        private const val KEY_FALLBACK_FORCED = "fallback.forced"

        /**
         * `androidx.security:security-crypto` hard-codes this alias inside
         * `MasterKey`. We delete it on recovery so the retry below gets a
         * freshly-generated AES-GCM key instead of reusing the stale one.
         */
        private const val MASTER_KEY_ALIAS = "_androidx_security_master_key_"

        private fun openEncryptedOrRecover(context: Context, name: String, fallbackName: String): SharedPreferences {
            val meta = context.getSharedPreferences("tpid_storage_meta_${name.takeLast(20)}", Context.MODE_PRIVATE)
            if (meta.getBoolean(KEY_FALLBACK_FORCED, false)) {
                Log.w("TpidStorage", "Using persistent fallback SharedPreferences")
                return context.getSharedPreferences(fallbackName, Context.MODE_PRIVATE)
            }
            // Attempt 1: the happy path.
            runCatching { return tryEncrypted(context, name) }
                .onFailure { first ->
                    Log.w("TpidStorage", "EncryptedSharedPreferences first attempt failed: ${first.javaClass.simpleName}: ${first.message}")
                    // Recovery is only warranted for known-broken states —
                    // `GeneralSecurityException` wraps the AEADBadTagException
                    // from `javax.crypto`, and `IllegalStateException` covers
                    // the "Invalid protobuf byte sequence" Tink also throws
                    // when the KeyStore entry and the prefs file diverge.
                    if (first is GeneralSecurityException || first is IllegalStateException) {
                        purgeStaleKeystoreAndPrefs(context, name)
                        runCatching { return tryEncrypted(context, name) }
                            .onFailure { second ->
                                Log.w("TpidStorage", "EncryptedSharedPreferences recovery failed: ${second.message}")
                                meta.edit().putBoolean(KEY_FALLBACK_FORCED, true).commit()
                            }
                    }
                }
            // Attempt 3: plain SharedPreferences. Tokens stored here will be
            // obfuscated by the encode/decode but not encrypted — callers
            // should treat this as degraded mode.
            Log.w("TpidStorage", "Falling back to plain SharedPreferences")
            meta.edit().putBoolean(KEY_FALLBACK_FORCED, true).commit()
            return context.getSharedPreferences(fallbackName, Context.MODE_PRIVATE)
        }

        private fun tryEncrypted(context: Context, name: String): SharedPreferences {
            val masterKey = MasterKey.Builder(context)
                .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
                .build()
            return EncryptedSharedPreferences.create(
                context,
                name,
                masterKey,
                EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
            )
        }

        private fun purgeStaleKeystoreAndPrefs(context: Context, name: String) {
            runCatching {
                @Suppress("DEPRECATION")
                if (!context.deleteSharedPreferences(name)) {
                    Log.w("TpidStorage", "deleteSharedPreferences($name) returned false")
                }
            }.onFailure { Log.w("TpidStorage", "deleteSharedPreferences: ${it.message}") }
            runCatching {
                val ks = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
                if (ks.containsAlias(MASTER_KEY_ALIAS)) {
                    ks.deleteEntry(MASTER_KEY_ALIAS)
                    Log.i("TpidStorage", "Deleted stale AndroidKeyStore alias $MASTER_KEY_ALIAS")
                }
            }.onFailure { Log.w("TpidStorage", "KeyStore purge: ${it.message}") }
        }
    }

    // ------------------------------------------------------------------ tokens

    @Serializable
    data class Tokens(
        val accessToken: String,
        val refreshToken: String?,
        val idToken: String?,
        val expiresAtMs: Long,
        val scope: String,
        val userDto: TpidUserDto? = null,
    ) {
        @Serializable
        data class TpidUserDto(
            val id: String,
            val email: String,
            val emailVerified: Boolean,
            val name: String? = null,
            val avatarUrl: String? = null,
            val locale: String? = null,
            val has2fa: Boolean = false,
            val hasPasskey: Boolean = false,
            val createdAt: String = "",
        ) {
            fun toPublic(): TpidUser = TpidUser(id, email, emailVerified, name, avatarUrl, locale, has2fa, hasPasskey, createdAt)
            companion object {
                fun from(u: TpidUser) = TpidUserDto(u.id, u.email, u.emailVerified, u.name, u.avatarUrl, u.locale, u.has2fa, u.hasPasskey, u.createdAt)
            }
        }

        val user: TpidUser? get() = userDto?.toPublic()
    }

    fun writeTokens(t: Tokens) {
        val raw = json.encodeToString(t)
        prefs.edit().putString(KEY_TOKENS, raw).commit()
        recoveryPrefs.edit().putString(KEY_TOKENS, raw).commit()
    }

    fun readTokens(): Tokens? {
        val raw = prefs.getString(KEY_TOKENS, null) ?: recoveryPrefs.getString(KEY_TOKENS, null) ?: return null
        return runCatching { json.decodeFromString<Tokens>(raw) }.getOrNull()
    }

    fun clearTokens() {
        prefs.edit().remove(KEY_TOKENS).commit()
        recoveryPrefs.edit().remove(KEY_TOKENS).commit()
    }

    // ------------------------------------------------------------------ pkce

    fun writePkce(verifier: String, state: String, nonce: String) {
        prefs.edit()
            .putString(KEY_PKCE_VERIFIER, verifier)
            .putString(KEY_PKCE_STATE, state)
            .putString(KEY_PKCE_NONCE, nonce)
            .apply()
    }

    data class PendingPkce(val verifier: String, val state: String, val nonce: String)

    fun readPkce(): PendingPkce? {
        val v = prefs.getString(KEY_PKCE_VERIFIER, null) ?: return null
        val s = prefs.getString(KEY_PKCE_STATE, null) ?: return null
        val n = prefs.getString(KEY_PKCE_NONCE, null) ?: return null
        return PendingPkce(v, s, n)
    }

    fun clearPkce() {
        prefs.edit().remove(KEY_PKCE_VERIFIER).remove(KEY_PKCE_STATE).remove(KEY_PKCE_NONCE).apply()
    }

    // ----------------------------------------------------------- generic kv

    fun putString(key: String, value: String?) {
        prefs.edit().apply { if (value == null) remove(key) else putString(key, value) }.apply()
    }

    fun getString(key: String): String? = prefs.getString(key, null)

    fun putLong(key: String, value: Long) {
        prefs.edit().putLong(key, value).apply()
    }

    fun getLong(key: String, default: Long = 0L): Long = prefs.getLong(key, default)

    // ----------------------------------------------------- account memory (2.6.0)

    /**
     * Minimal profile kept across sign-outs so the widget can render a
     * "Continue as <name/email>" welcome card on next open. Deliberately a
     * subset of `Tokens.user` — no tokens, no scopes, no IDs — so it's safe
     * to leave when the user explicitly signs out.
     */
    data class LastAccount(val email: String, val displayName: String?, val avatarUrl: String?, val lastAuthenticatedAtMs: Long)

    fun writeLastAccount(email: String, name: String?, avatarUrl: String?) {
        val ts = System.currentTimeMillis()
        val e = prefs.edit()
            .putString(KEY_LAST_EMAIL, email)
            .putLong(KEY_LAST_AUTH_AT, ts)
            .apply {
                if (name.isNullOrBlank()) remove(KEY_LAST_NAME) else putString(KEY_LAST_NAME, name)
                if (avatarUrl.isNullOrBlank()) remove(KEY_LAST_AVATAR) else putString(KEY_LAST_AVATAR, avatarUrl)
            }
        e.commit()
        val r = recoveryPrefs.edit()
            .putString(KEY_LAST_EMAIL, email)
            .putLong(KEY_LAST_AUTH_AT, ts)
            .apply {
                if (name.isNullOrBlank()) remove(KEY_LAST_NAME) else putString(KEY_LAST_NAME, name)
                if (avatarUrl.isNullOrBlank()) remove(KEY_LAST_AVATAR) else putString(KEY_LAST_AVATAR, avatarUrl)
            }
        r.commit()
    }

    fun readLastAccount(): LastAccount? {
        val source = if (prefs.contains(KEY_LAST_EMAIL)) prefs else recoveryPrefs
        val email = source.getString(KEY_LAST_EMAIL, null)?.takeIf { it.isNotBlank() } ?: return null
        val name = source.getString(KEY_LAST_NAME, null)?.takeIf { it.isNotBlank() }
        val avatar = source.getString(KEY_LAST_AVATAR, null)?.takeIf { it.isNotBlank() }
        val authAt = source.getLong(KEY_LAST_AUTH_AT, 0L)
        return LastAccount(email, name, avatar, authAt)
    }

    fun clearLastAccount() {
        prefs.edit()
            .remove(KEY_LAST_EMAIL)
            .remove(KEY_LAST_NAME)
            .remove(KEY_LAST_AVATAR)
            .remove(KEY_LAST_AUTH_AT)
            .commit()
        recoveryPrefs.edit()
            .remove(KEY_LAST_EMAIL)
            .remove(KEY_LAST_NAME)
            .remove(KEY_LAST_AVATAR)
            .remove(KEY_LAST_AUTH_AT)
            .commit()
    }
}
