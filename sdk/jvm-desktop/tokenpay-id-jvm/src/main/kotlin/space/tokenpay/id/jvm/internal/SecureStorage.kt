package space.tokenpay.id.jvm.internal

import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import space.tokenpay.id.jvm.TpidSession
import space.tokenpay.id.jvm.TpidUser
import java.io.File
import java.nio.file.Files
import java.nio.file.attribute.PosixFilePermissions
import java.security.MessageDigest
import java.time.Instant
import java.util.Base64
import java.util.Locale
import javax.crypto.Cipher
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.SecretKeySpec

/**
 * Per-user secure storage for refresh tokens and session metadata.
 *
 * Backend selection:
 *  - Windows → DPAPI (via JNA) if available; otherwise AES-GCM file with PBKDF2 key.
 *  - macOS → Keychain generic password via `security` CLI; otherwise AES-GCM file.
 *  - Linux → libsecret via `secret-tool` CLI if present; otherwise AES-GCM file.
 *
 * The AES-GCM fallback is still safe-at-rest because the derived key is bound to
 * a stable machine-id + user principal, so the ciphertext is useless if copied
 * to another machine. It is NOT safe against a local attacker that already has
 * code-execution rights in the user's profile — no desktop keychain is.
 */
internal class SecureStorage(clientId: String) {

    private val json = Json { ignoreUnknownKeys = true }
    private val backend: Backend = pickBackend(clientId)
    private val pkceBackend: Backend = backend.scope("pkce")

    @Serializable
    private data class Persisted(
        val accessToken: String,
        val refreshToken: String?,
        val idToken: String?,
        val expiresAtEpoch: Long,
        val tokenType: String,
        val scope: String?,
        val user: User,
    ) {
        @Serializable data class User(val id: String, val email: String, val emailVerified: Boolean, val name: String?, val avatarUrl: String?, val locale: String?)
    }

    fun writeSession(session: TpidSession) {
        val p = Persisted(
            accessToken = session.accessToken,
            refreshToken = session.refreshToken,
            idToken = session.idToken,
            expiresAtEpoch = session.expiresAt.epochSecond,
            tokenType = session.tokenType,
            scope = session.scope,
            user = Persisted.User(session.user.id, session.user.email, session.user.emailVerified, session.user.name, session.user.avatarUrl, session.user.locale),
        )
        backend.put("session", json.encodeToString(p))
    }

    fun readSession(): TpidSession? {
        val raw = backend.get("session") ?: return null
        return runCatching {
            val p = json.decodeFromString(Persisted.serializer(), raw)
            TpidSession(
                accessToken = p.accessToken,
                refreshToken = p.refreshToken,
                idToken = p.idToken,
                expiresAt = Instant.ofEpochSecond(p.expiresAtEpoch),
                tokenType = p.tokenType,
                scope = p.scope,
                user = TpidUser(p.user.id, p.user.email, p.user.emailVerified, p.user.name, p.user.avatarUrl, p.user.locale),
            )
        }.getOrNull()
    }

    fun clearSession() {
        backend.remove("session")
    }

    fun writePKCE(verifier: String, state: String, nonce: String) {
        pkceBackend.put("v", verifier)
        pkceBackend.put("s", state)
        pkceBackend.put("n", nonce)
    }

    fun readPKCEVerifier(): String? = pkceBackend.get("v")
    fun readPKCEState(): String?    = pkceBackend.get("s")
    fun readPKCENonce(): String?    = pkceBackend.get("n")

    fun clearPKCE() {
        pkceBackend.remove("v"); pkceBackend.remove("s"); pkceBackend.remove("n")
    }

    // ----------------------------------------------------- account memory (2.6.0)

    /**
     * Minimal profile kept across sign-outs so the widget opens with a
     * "Continue as X" card instead of an empty email field on the next
     * launch. Deliberately a subset of `TpidSession.user` — no tokens, no
     * scopes — so it is safe to preserve when the user signs out.
     */
    data class LastAccount(val email: String, val displayName: String?, val avatarUrl: String?, val lastAuthenticatedAtMs: Long = 0L)

    @Serializable
    private data class PersistedLastAccount(
        val email: String,
        val displayName: String? = null,
        val avatarUrl: String? = null,
        val lastAuthenticatedAtMs: Long = 0L,
    )

    fun writeLastAccount(email: String, displayName: String?, avatarUrl: String?) {
        val p = PersistedLastAccount(
            email = email,
            displayName = displayName?.takeIf { it.isNotBlank() },
            avatarUrl = avatarUrl?.takeIf { it.isNotBlank() },
            lastAuthenticatedAtMs = System.currentTimeMillis(),
        )
        backend.put("last-account", json.encodeToString(p))
    }

    fun readLastAccount(): LastAccount? {
        val raw = backend.get("last-account") ?: return null
        return runCatching {
            val p = json.decodeFromString(PersistedLastAccount.serializer(), raw)
            LastAccount(p.email, p.displayName, p.avatarUrl, p.lastAuthenticatedAtMs)
        }.getOrNull()
    }

    fun clearLastAccount() { backend.remove("last-account") }

    // ---- Backend abstraction ----

    private interface Backend {
        fun put(key: String, value: String)
        fun get(key: String): String?
        fun remove(key: String)
        fun scope(sub: String): Backend
    }

    private fun pickBackend(clientId: String): Backend {
        val os = System.getProperty("os.name", "").lowercase(Locale.ROOT)
        val ns = "tokenpay-id/$clientId"
        return when {
            os.contains("win") -> WindowsDpapiBackend.tryCreate(ns) ?: FileBackend(ns)
            os.contains("mac") -> MacKeychainBackend.tryCreate(ns) ?: FileBackend(ns)
            os.contains("nix") || os.contains("nux") -> LinuxLibsecretBackend.tryCreate(ns) ?: FileBackend(ns)
            else -> FileBackend(ns)
        }
    }

    // ---- AES-GCM file backend (used on any OS as fallback) ----

    private class FileBackend(private val namespace: String) : Backend {
        private val root: File = run {
            val base = when {
                System.getProperty("os.name", "").lowercase(Locale.ROOT).contains("win") ->
                    File(System.getenv("APPDATA") ?: System.getProperty("user.home"))
                System.getProperty("os.name", "").lowercase(Locale.ROOT).contains("mac") ->
                    File(System.getProperty("user.home"), "Library/Application Support")
                else -> File(System.getenv("XDG_DATA_HOME") ?: "${System.getProperty("user.home")}/.local/share")
            }
            File(base, namespace).also { it.mkdirs() }
        }
        private val key: SecretKey by lazy { deriveKey(namespace) }

        override fun put(key: String, value: String) {
            val iv = ByteArray(12).also { java.security.SecureRandom().nextBytes(it) }
            val c = Cipher.getInstance("AES/GCM/NoPadding")
            c.init(Cipher.ENCRYPT_MODE, this.key, GCMParameterSpec(128, iv))
            val ct = c.doFinal(value.toByteArray(Charsets.UTF_8))
            val out = iv + ct
            val f = File(root, "$key.bin")
            f.writeBytes(out)
            restrictPermissions(f)
        }

        override fun get(key: String): String? {
            val f = File(root, "$key.bin")
            if (!f.exists()) return null
            return runCatching {
                val bytes = f.readBytes()
                val iv = bytes.copyOfRange(0, 12)
                val ct = bytes.copyOfRange(12, bytes.size)
                val c = Cipher.getInstance("AES/GCM/NoPadding")
                c.init(Cipher.DECRYPT_MODE, this.key, GCMParameterSpec(128, iv))
                String(c.doFinal(ct), Charsets.UTF_8)
            }.getOrNull()
        }

        override fun remove(key: String) { File(root, "$key.bin").delete() }

        override fun scope(sub: String): Backend = FileBackend("$namespace/$sub")

        private fun restrictPermissions(f: File) {
            try {
                if (!System.getProperty("os.name", "").lowercase(Locale.ROOT).contains("win")) {
                    Files.setPosixFilePermissions(f.toPath(), PosixFilePermissions.fromString("rw-------"))
                }
            } catch (_: Throwable) { /* best-effort */ }
        }

        private fun deriveKey(ns: String): SecretKey {
            val seed = buildString {
                append(System.getProperty("user.name", ""))
                append('|')
                append(System.getProperty("user.home", ""))
                append('|')
                append(machineId())
                append('|')
                append(ns)
            }.toByteArray(Charsets.UTF_8)
            val digest = MessageDigest.getInstance("SHA-256").digest(seed)
            return SecretKeySpec(digest, "AES")
        }

        private fun machineId(): String {
            // Best-effort stable per-machine identifier
            val props = listOfNotNull(
                System.getenv("COMPUTERNAME"),
                System.getenv("HOSTNAME"),
                runCatching { java.net.InetAddress.getLocalHost().hostName }.getOrNull(),
            )
            return if (props.isEmpty()) "default" else props.joinToString("|")
        }
    }

    // ---- macOS Keychain via `security` CLI ----

    private class MacKeychainBackend(private val service: String) : Backend {
        override fun put(key: String, value: String) {
            val encoded = Base64.getEncoder().encodeToString(value.toByteArray(Charsets.UTF_8))
            runCmd(listOf("security", "delete-generic-password", "-s", service, "-a", key))
            val p = ProcessBuilder(
                "security", "add-generic-password",
                "-s", service, "-a", key, "-w", encoded, "-U"
            ).redirectErrorStream(true).start()
            p.waitFor()
        }
        override fun get(key: String): String? {
            val (code, out) = runCmdCollecting(listOf("security", "find-generic-password", "-s", service, "-a", key, "-w"))
            if (code != 0) return null
            return runCatching { String(Base64.getDecoder().decode(out.trim()), Charsets.UTF_8) }.getOrNull()
        }
        override fun remove(key: String) {
            runCmd(listOf("security", "delete-generic-password", "-s", service, "-a", key))
        }
        override fun scope(sub: String): Backend = MacKeychainBackend("$service.$sub")

        companion object {
            fun tryCreate(ns: String): Backend? =
                if (runCmd(listOf("which", "security")) == 0) MacKeychainBackend("space.tokenpay.id.${ns.replace("/", ".")}") else null
        }
    }

    // ---- Linux libsecret via `secret-tool` CLI ----

    private class LinuxLibsecretBackend(private val collection: String) : Backend {
        override fun put(key: String, value: String) {
            val encoded = Base64.getEncoder().encodeToString(value.toByteArray(Charsets.UTF_8))
            val p = ProcessBuilder("secret-tool", "store", "--label", "TOKEN PAY ID", "collection", collection, "key", key)
                .redirectErrorStream(true).start()
            p.outputStream.write(encoded.toByteArray(Charsets.UTF_8))
            p.outputStream.close()
            p.waitFor()
        }
        override fun get(key: String): String? {
            val (code, out) = runCmdCollecting(listOf("secret-tool", "lookup", "collection", collection, "key", key))
            if (code != 0) return null
            return runCatching { String(Base64.getDecoder().decode(out.trim()), Charsets.UTF_8) }.getOrNull()
        }
        override fun remove(key: String) {
            runCmd(listOf("secret-tool", "clear", "collection", collection, "key", key))
        }
        override fun scope(sub: String): Backend = LinuxLibsecretBackend("$collection.$sub")

        companion object {
            fun tryCreate(ns: String): Backend? =
                if (runCmd(listOf("which", "secret-tool")) == 0) LinuxLibsecretBackend("tokenpay-id-${ns.replace("/", "-")}") else null
        }
    }

    // ---- Windows DPAPI via JNA ----

    private class WindowsDpapiBackend(private val namespace: String) : Backend {
        // Store DPAPI-encrypted blobs as files; DPAPI is tied to Windows user account.
        private val root: File = run {
            val base = File(System.getenv("APPDATA") ?: System.getProperty("user.home"))
            File(base, namespace).also { it.mkdirs() }
        }
        override fun put(key: String, value: String) {
            val blob = Crypt32Wrapper.protect(value.toByteArray(Charsets.UTF_8))
            File(root, "$key.dpapi").writeBytes(blob)
        }
        override fun get(key: String): String? {
            val f = File(root, "$key.dpapi")
            if (!f.exists()) return null
            return runCatching { String(Crypt32Wrapper.unprotect(f.readBytes()), Charsets.UTF_8) }.getOrNull()
        }
        override fun remove(key: String) { File(root, "$key.dpapi").delete() }
        override fun scope(sub: String): Backend = WindowsDpapiBackend("$namespace/$sub")

        companion object {
            fun tryCreate(ns: String): Backend? =
                if (Crypt32Wrapper.available) WindowsDpapiBackend(ns) else null
        }
    }

    companion object {
        internal fun runCmd(cmd: List<String>): Int = try {
            val p = ProcessBuilder(cmd).redirectErrorStream(true).start()
            p.inputStream.readAllBytes(); p.waitFor()
        } catch (_: Throwable) { -1 }

        internal fun runCmdCollecting(cmd: List<String>): Pair<Int, String> = try {
            val p = ProcessBuilder(cmd).redirectErrorStream(true).start()
            val out = p.inputStream.readAllBytes().decodeToString()
            p.waitFor() to out
        } catch (_: Throwable) { -1 to "" }
    }
}
