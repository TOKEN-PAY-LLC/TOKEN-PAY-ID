package space.tokenpay.id.internal

import android.graphics.Bitmap
import android.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import com.google.zxing.BarcodeFormat
import com.google.zxing.EncodeHintType
import com.google.zxing.qrcode.QRCodeWriter
import com.google.zxing.qrcode.decoder.ErrorCorrectionLevel

/**
 * Renders [text] (typically a `tokenpay.space/qr-login?sid=…` URL from
 * `/auth/qr/login-init`) as a crisp black-and-white QR code suitable for
 * scanning with a phone camera. Uses ZXing with ECC-M (matches the web
 * widget) and a 1-module quiet zone so the widget still scans when scaled
 * down to ~200 dp.
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
            val bmp = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888)
            for (y in 0 until h) {
                for (x in 0 until w) {
                    bmp.setPixel(x, y, if (matrix.get(x, y)) Color.BLACK else Color.WHITE)
                }
            }
            bmp.asImageBitmap()
        }.getOrNull()
    }
}
