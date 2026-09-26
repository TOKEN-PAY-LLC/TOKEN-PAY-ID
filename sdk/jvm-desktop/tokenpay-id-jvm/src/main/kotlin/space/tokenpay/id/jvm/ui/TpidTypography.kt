package space.tokenpay.id.jvm

import androidx.compose.material3.Typography
import androidx.compose.runtime.Composable
import androidx.compose.ui.res.useResource
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.platform.Font
import androidx.compose.ui.unit.sp

/**
 * Comfortaa — loaded from the bundled variable TTF resource.
 *
 * Using a single variable font means we don't need separate regular / medium /
 * bold files and we stay well below any JAR-size budget.
 *
 * Historical note (pre-2.5.0-pre.3): this file called `Font(resource = "…")`
 * — the Android-only signature — and did not compile at all on Compose
 * Desktop. Switched to the Skiko path `Font(identity, data, weight, style)`
 * with a cached ByteArray loaded from the classpath via `useResource`.
 */
object TpidFonts {
    /** Load the TTF bytes once so the four weights share a single buffer. */
    private val comfortaaBytes: ByteArray by lazy {
        useResource("fonts/Comfortaa-Variable.ttf") { it.readBytes() }
    }

    val Comfortaa: FontFamily by lazy {
        FontFamily(
            Font(identity = "Comfortaa-Regular",  data = comfortaaBytes, weight = FontWeight.Normal,   style = FontStyle.Normal),
            Font(identity = "Comfortaa-Medium",   data = comfortaaBytes, weight = FontWeight.Medium,   style = FontStyle.Normal),
            Font(identity = "Comfortaa-SemiBold", data = comfortaaBytes, weight = FontWeight.SemiBold, style = FontStyle.Normal),
            Font(identity = "Comfortaa-Bold",     data = comfortaaBytes, weight = FontWeight.Bold,     style = FontStyle.Normal),
        )
    }
}

/**
 * Official TOKEN PAY ID typography. All text in the widget renders with
 * Comfortaa — the same face used by tokenpay.space — so desktop and web
 * widgets feel like the same product.
 *
 * Font sizes are kept close to the Material-3 defaults but slightly tightened
 * to read well at widget density.
 */
@Composable
fun tpidTypography(): Typography {
    val base = Comfortaa
    return Typography(
        displayLarge    = TextStyle(fontFamily = base, fontWeight = FontWeight.Bold,    fontSize = 40.sp, letterSpacing = (-0.5).sp),
        displayMedium   = TextStyle(fontFamily = base, fontWeight = FontWeight.Bold,    fontSize = 32.sp, letterSpacing = (-0.4).sp),
        displaySmall    = TextStyle(fontFamily = base, fontWeight = FontWeight.Bold,    fontSize = 26.sp, letterSpacing = (-0.2).sp),
        headlineLarge   = TextStyle(fontFamily = base, fontWeight = FontWeight.Bold,    fontSize = 24.sp, letterSpacing = (-0.2).sp),
        headlineMedium  = TextStyle(fontFamily = base, fontWeight = FontWeight.Bold,    fontSize = 20.sp, letterSpacing = 0.sp),
        headlineSmall   = TextStyle(fontFamily = base, fontWeight = FontWeight.SemiBold,fontSize = 17.sp, letterSpacing = 0.sp),
        titleLarge      = TextStyle(fontFamily = base, fontWeight = FontWeight.Bold,    fontSize = 18.sp, letterSpacing = 0.sp),
        titleMedium     = TextStyle(fontFamily = base, fontWeight = FontWeight.SemiBold,fontSize = 15.sp, letterSpacing = 0.1.sp),
        titleSmall      = TextStyle(fontFamily = base, fontWeight = FontWeight.SemiBold,fontSize = 13.sp, letterSpacing = 0.1.sp),
        bodyLarge       = TextStyle(fontFamily = base, fontWeight = FontWeight.Normal,  fontSize = 15.sp, letterSpacing = 0.15.sp),
        bodyMedium      = TextStyle(fontFamily = base, fontWeight = FontWeight.Normal,  fontSize = 13.sp, letterSpacing = 0.15.sp),
        bodySmall       = TextStyle(fontFamily = base, fontWeight = FontWeight.Normal,  fontSize = 11.sp, letterSpacing = 0.2.sp),
        labelLarge      = TextStyle(fontFamily = base, fontWeight = FontWeight.SemiBold,fontSize = 14.sp, letterSpacing = 0.2.sp),
        labelMedium     = TextStyle(fontFamily = base, fontWeight = FontWeight.SemiBold,fontSize = 12.sp, letterSpacing = 0.3.sp),
        labelSmall      = TextStyle(fontFamily = base, fontWeight = FontWeight.Bold,    fontSize = 10.sp, letterSpacing = 1.2.sp),
    )
}

private val Comfortaa: FontFamily get() = TpidFonts.Comfortaa
