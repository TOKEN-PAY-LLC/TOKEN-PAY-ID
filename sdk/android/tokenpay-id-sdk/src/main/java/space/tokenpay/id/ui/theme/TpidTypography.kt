package space.tokenpay.id.ui.theme

import androidx.compose.material3.Typography
import androidx.compose.runtime.Composable
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import space.tokenpay.id.R

/**
 * Comfortaa is the official TOKEN PAY ID wordmark font. A single **variable**
 * TTF covers every weight we use, so we pay the 200 KB cost once and get
 * pixel-perfect parity with the web widget at id.tokenpay.space and
 * auth.tokenpay.space.
 *
 * Keep this file aligned with the JVM/Swift equivalents
 * (`TpidTypography.kt` and `TpidTypography.swift`).
 */
private val ComfortaaFamily: FontFamily = FontFamily(
    Font(R.font.comfortaa_variable, FontWeight.Light),
    Font(R.font.comfortaa_variable, FontWeight.Normal),
    Font(R.font.comfortaa_variable, FontWeight.Medium),
    Font(R.font.comfortaa_variable, FontWeight.SemiBold),
    Font(R.font.comfortaa_variable, FontWeight.Bold),
)

@Composable
internal fun tpidTypography(): Typography {
    val base = Typography()
    fun TextStyle.w(w: FontWeight) = copy(fontFamily = ComfortaaFamily, fontWeight = w)
    return Typography(
        displayLarge   = base.displayLarge.w(FontWeight.Bold),
        displayMedium  = base.displayMedium.w(FontWeight.Bold),
        displaySmall   = base.displaySmall.w(FontWeight.Bold),
        headlineLarge  = base.headlineLarge.w(FontWeight.Bold),
        headlineMedium = base.headlineMedium.w(FontWeight.Bold),
        headlineSmall  = base.headlineSmall.w(FontWeight.SemiBold),
        titleLarge     = base.titleLarge.w(FontWeight.SemiBold),
        titleMedium    = base.titleMedium.w(FontWeight.SemiBold),
        titleSmall     = base.titleSmall.w(FontWeight.Medium),
        bodyLarge      = base.bodyLarge.w(FontWeight.Normal),
        bodyMedium     = base.bodyMedium.w(FontWeight.Normal),
        bodySmall      = base.bodySmall.w(FontWeight.Normal),
        labelLarge     = base.labelLarge.w(FontWeight.SemiBold),
        labelMedium    = base.labelMedium.w(FontWeight.SemiBold),
        labelSmall     = base.labelSmall.w(FontWeight.Medium),
    )
}
