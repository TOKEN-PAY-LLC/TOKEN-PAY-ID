package space.tokenpay.id.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import space.tokenpay.id.TpidConfig

// Card background (login.html .auth-card): rgba(7,7,9,.88) with backdrop-filter blur.
// Native widget is opaque — so use a slightly lifted #0E0E11 atop pure black page.
private val LightColors = lightColorScheme(
    primary = Color(0xFF0B0B0D),
    onPrimary = Color(0xFFFFFFFF),
    primaryContainer = Color(0xFF0B0B0D),
    onPrimaryContainer = Color(0xFFFFFFFF),
    secondary = Color(0xFF2A2A2E),
    onSecondary = Color(0xFFFFFFFF),
    background = Color(0xFFF5F5F7),
    onBackground = Color(0xFF0B0B0D),
    surface = Color(0xFFFFFFFF),
    onSurface = Color(0xFF0B0B0D),
    surfaceVariant = Color(0xFFEEEEF0),
    onSurfaceVariant = Color(0xFF55555A),
    outline = Color(0xFFDCDCE0),
    // 2.6.0: strict-monochrome — `error` matches `onBackground` so any
    // widget surface that still reads `colorScheme.error` (3rd-party
    // composables, Android system a11y) stays on the black-and-white
    // palette instead of bleeding a red accent into the widget.
    error = Color(0xFF0B0B0D),
    onError = Color(0xFFFFFFFF),
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFFFFFFFF),
    onPrimary = Color(0xFF0B0B0D),
    primaryContainer = Color(0xFFFFFFFF),
    onPrimaryContainer = Color(0xFF0B0B0D),
    secondary = Color(0xFFCCCCCC),
    onSecondary = Color(0xFF0B0B0D),
    background = Color(0xFF050507),
    onBackground = Color(0xFFF5F5F7),
    surface = Color(0xFF0E0E11),
    onSurface = Color(0xFFF5F5F7),
    surfaceVariant = Color(0xFF14141A),
    onSurfaceVariant = Color(0xFFB3B3BA),
    outline = Color(0xFF2A2A31),
    // 2.6.0: strict-monochrome error matches `onBackground` on dark theme.
    error = Color(0xFFF5F5F7),
    onError = Color(0xFF0B0B0D),
)

@Composable
fun TpidTheme(
    themeMode: TpidConfig.Theme = TpidConfig.Theme.AUTO,
    content: @Composable () -> Unit,
) {
    val dark = when (themeMode) {
        TpidConfig.Theme.LIGHT -> false
        TpidConfig.Theme.DARK -> true
        TpidConfig.Theme.AUTO -> isSystemInDarkTheme()
    }
    MaterialTheme(
        colorScheme = if (dark) DarkColors else LightColors,
        typography = tpidTypography(),
        content = content,
    )
}
