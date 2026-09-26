package space.tokenpay.id.jvm.internal

import com.sun.jna.Library
import com.sun.jna.Memory
import com.sun.jna.Native
import com.sun.jna.Pointer
import com.sun.jna.Structure

/**
 * Top-level, open Structure subclass — JNA reflects over fields here, so the class
 * must (a) be public / package-visible, (b) be non-final (open), and (c) declare
 * field order via the @Structure.FieldOrder annotation. Previous nested-inside-
 * an-object form triggered "Exception reading field 'cbData'" on JDK 17+.
 */
@Structure.FieldOrder("cbData", "pbData")
open class Crypt32DataBlob : Structure() {
    @JvmField var cbData: Int = 0
    @JvmField var pbData: Pointer? = null
    class ByValue : Crypt32DataBlob(), Structure.ByValue
    class ByReference : Crypt32DataBlob(), Structure.ByReference
}

/**
 * Minimal JNA wrapper around Windows DPAPI (Crypt32.dll).
 *
 * Provides per-user, per-machine encryption of byte blobs. The OS handles the
 * actual key material. Useless outside the current Windows user's session.
 */
internal object Crypt32Wrapper {

    private interface Crypt32 : Library {
        fun CryptProtectData(
            pDataIn: Crypt32DataBlob,
            szDataDescr: String?,
            pOptionalEntropy: Crypt32DataBlob?,
            pvReserved: Pointer?,
            pPromptStruct: Pointer?,
            dwFlags: Int,
            pDataOut: Crypt32DataBlob
        ): Boolean

        fun CryptUnprotectData(
            pDataIn: Crypt32DataBlob,
            ppszDataDescr: Pointer?,
            pOptionalEntropy: Crypt32DataBlob?,
            pvReserved: Pointer?,
            pPromptStruct: Pointer?,
            dwFlags: Int,
            pDataOut: Crypt32DataBlob
        ): Boolean
    }

    private interface Kernel32 : Library {
        fun LocalFree(hMem: Pointer?): Pointer?
    }

    private val crypt32: Crypt32? = safeLoad {
        @Suppress("UNCHECKED_CAST")
        Native.load("Crypt32", Crypt32::class.java) as Crypt32
    }

    private val kernel32: Kernel32? = safeLoad {
        @Suppress("UNCHECKED_CAST")
        Native.load("Kernel32", Kernel32::class.java) as Kernel32
    }

    val available: Boolean get() = crypt32 != null && kernel32 != null

    fun protect(data: ByteArray): ByteArray = callDpapi(data, encrypt = true)

    fun unprotect(data: ByteArray): ByteArray = callDpapi(data, encrypt = false)

    private fun callDpapi(data: ByteArray, encrypt: Boolean): ByteArray {
        val c = crypt32 ?: error("Crypt32 not available")
        val k = kernel32 ?: error("Kernel32 not available")
        val input = Crypt32DataBlob().apply {
            cbData = data.size
            val mem = Memory(data.size.toLong().coerceAtLeast(1))
            if (data.isNotEmpty()) mem.write(0, data, 0, data.size)
            pbData = mem
        }
        // Write input fields to native memory BEFORE the call — JNA will then
        // auto-read output fields back into the Kotlin fields after the call.
        input.write()
        val output = Crypt32DataBlob()
        val ok = if (encrypt) c.CryptProtectData(input, null, null, null, null, 0, output)
                 else c.CryptUnprotectData(input, null, null, null, null, 0, output)
        if (!ok) {
            val err = Native.getLastError()
            throw RuntimeException("${if (encrypt) "CryptProtectData" else "CryptUnprotectData"} failed (error=$err)")
        }
        // Populate Kotlin fields from native memory explicitly — belt-and-braces
        // in case auto-read didn't fire for a by-value return.
        output.read()
        val ptr = output.pbData ?: throw RuntimeException("DPAPI returned null pbData")
        val out = ptr.getByteArray(0, output.cbData)
        k.LocalFree(ptr)
        return out
    }

    private inline fun <T> safeLoad(block: () -> T): T? = try { block() } catch (_: Throwable) { null }
}
