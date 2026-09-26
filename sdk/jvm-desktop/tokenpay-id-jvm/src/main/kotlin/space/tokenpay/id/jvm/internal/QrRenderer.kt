package space.tokenpay.id.jvm.internal

import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.toComposeImageBitmap
import com.google.zxing.BarcodeFormat
import com.google.zxing.EncodeHintType
import com.google.zxing.qrcode.QRCodeWriter
import com.google.zxing.qrcode.decoder.ErrorCorrectionLevel
import java.awt.image.BufferedImage

/**
 * Converts an arbitrary UTF-8 payload (typically a `tokenpay.space/qr-login?sid=…`
 * URL returned by `POST /auth/qr/login-init`) into a crisp black-and-white
 * [ImageBitmap] at [pixelSize] × [pixelSize].
 *
 * Rendered via ZXing with ECC-M (15 % error correction, same as the web widget
 * and /qr-login page) and a 1-module quiet zone so integrators that scale the
 * output down to ~180–220 dp still get a scannable code on phone cameras.
 *
 * The result goes through a [BufferedImage] to [ImageBitmap] hop — simple,
 * portable across Windows/Linux/macOS, and costs <5 ms for a 512² QR at
 * integrator startup (called once per session).
 */
internal object QrRenderer {

    fun render(text: String, pixelSize: Int = 512): ImageBitmap? {
        if (text.isBlank()) return null
        return runCatching {
            val hints = mapOf(
                EncodeHintType.ERROR_CORRECTION to ErrorCorrectionLevel.M,
                EncodeHintType.MARGIN to 1,
                EncodeHintType.CHARACTER_SET to "UTF-8",
            )
            val matrix = QRCodeWriter().encode(
                text, BarcodeFormat.QR_CODE,
                pixelSize, pixelSize, hints,
            )
            val w = matrix.width
            val h = matrix.height
            val img = BufferedImage(w, h, BufferedImage.TYPE_INT_ARGB)
            for (y in 0 until h) {
                for (x in 0 until w) {
                    // ZXing convention: true = black module, false = white.
                    img.setRGB(x, y, if (matrix.get(x, y)) 0xFF000000.toInt() else 0xFFFFFFFF.toInt())
                }
            }
            img.toComposeImageBitmap()
        }.getOrNull()
    }
}
