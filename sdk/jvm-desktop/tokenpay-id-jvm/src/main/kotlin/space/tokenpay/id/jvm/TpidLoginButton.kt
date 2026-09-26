package space.tokenpay.id.jvm

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsHoveredAsState
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.hoverable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ColorFilter
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

/** Visual variants for [TpidLoginButton]. */
enum class TpidButtonVariant { DARK, LIGHT, ICON_ONLY }

/** Size presets matching the official design system. */
enum class TpidButtonSize { SMALL, MEDIUM, LARGE }

/**
 * [height]   — overall button height.
 * [wordmark] — height of the wordmark image (DARK / LIGHT variants).
 * [icon]     — size of the single-glyph icon (ICON_ONLY variant).
 * [padH]     — horizontal padding around the wordmark.
 */
private data class BtnDims(val height: Dp, val wordmark: Dp, val icon: Dp, val padH: Dp)

private fun TpidButtonSize.dims(): BtnDims = when (this) {
    // Wordmarks are slightly larger than the old values — on Image 2 the white
    // wordmark on the dark pill visibly "vanished" next to its neighbour, so we
    // bump both variants evenly and keep them identical between DARK and LIGHT.
    TpidButtonSize.SMALL  -> BtnDims(height = 40.dp, wordmark = 18.dp, icon = 22.dp, padH = 20.dp)
    TpidButtonSize.MEDIUM -> BtnDims(height = 48.dp, wordmark = 22.dp, icon = 28.dp, padH = 26.dp)
    TpidButtonSize.LARGE  -> BtnDims(height = 56.dp, wordmark = 26.dp, icon = 34.dp, padH = 32.dp)
}

/**
 * Official TOKEN PAY ID login button. Displays only the brand logo — no text —
 * so every integration across apps and platforms looks identical.
 *
 * ```kotlin
 * TpidLoginButton(variant = TpidButtonVariant.DARK) { result -> … }
 * ```
 */
@Composable
fun TpidLoginButton(
    modifier: Modifier = Modifier,
    variant: TpidButtonVariant = TpidButtonVariant.DARK,
    size: TpidButtonSize = TpidButtonSize.MEDIUM,
    fullWidth: Boolean = false,
    loading: Boolean = false,
    onResult: (TpidResult) -> Unit,
) {
    var showWidget by remember { mutableStateOf(false) }
    val enabled = !loading
    val d = size.dims()

    // Shared interaction source drives both hover and press animations so the
    // DARK and LIGHT buttons feel identical.
    val interaction = remember { MutableInteractionSource() }
    val hovered by interaction.collectIsHoveredAsState()
    val pressed by interaction.collectIsPressedAsState()
    val scale by animateFloatAsState(
        targetValue = if (pressed) 0.965f else if (hovered) 1.015f else 1.0f,
        animationSpec = spring(dampingRatio = 0.6f, stiffness = 520f),
        label = "tpid-btn-scale",
    )

    when (variant) {
        TpidButtonVariant.DARK, TpidButtonVariant.LIGHT -> {
            val dark = variant == TpidButtonVariant.DARK
            val bg = if (dark) Color(0xFF0B0B0D) else Color.White
            // Keep the two borders visually equal-weight: both sit ~14 % away
            // from the background, so the outline "strength" is the same
            // regardless of theme.
            val borderCol = if (dark) Color.White.copy(alpha = 0.28f) else Color(0xFF0B0B0D).copy(alpha = 0.28f)
            val wordmark = if (dark) "tpid_wordmark_white.png" else "tpid_wordmark_black.png"
            val fg = if (dark) Color.White else Color(0xFF0B0B0D)
            val shadowAlpha = if (dark) 0.5f else 0.18f
            Row(
                modifier = modifier
                    .then(if (fullWidth) Modifier.fillMaxWidth() else Modifier)
                    .heightIn(min = d.height)
                    .scale(scale)
                    .shadow(
                        elevation = if (hovered) 10.dp else 4.dp,
                        shape = RoundedCornerShape(999.dp),
                        clip = false,
                        ambientColor = Color.Black.copy(alpha = shadowAlpha),
                        spotColor = Color.Black.copy(alpha = shadowAlpha),
                    )
                    .clip(RoundedCornerShape(999.dp))
                    .background(bg)
                    .border(2.dp, borderCol, RoundedCornerShape(999.dp))
                    .hoverable(interaction)
                    .clickable(interactionSource = interaction, indication = null, enabled = enabled) {
                        showWidget = true
                    }
                    .padding(horizontal = d.padH, vertical = 8.dp),
                horizontalArrangement = Arrangement.Center,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                if (loading) {
                    CircularProgressIndicator(
                        strokeWidth = 2.dp, color = fg,
                        modifier = Modifier.size(d.wordmark),
                    )
                } else {
                    Image(
                        painter = painterResource(wordmark),
                        contentDescription = "Sign in with TOKEN PAY ID",
                        modifier = Modifier.height(d.wordmark),
                    )
                }
            }
        }
        TpidButtonVariant.ICON_ONLY -> {
            // White-on-black circular button with the saturn logo, matching
            // the round brand badge shown on tokenpay.space's hero header.
            // A faint white ring sits at the button's edge so it reads as a
            // deliberate "pill" instead of a flat black disc.
            Box(
                modifier = modifier
                    .size(d.height)
                    .scale(scale)
                    .shadow(
                        elevation = if (hovered) 10.dp else 4.dp,
                        shape = CircleShape,
                        clip = false,
                        ambientColor = Color.Black.copy(alpha = 0.45f),
                        spotColor = Color.Black.copy(alpha = 0.45f),
                    )
                    .clip(CircleShape)
                    .background(Color(0xFF0B0B0D))
                    .border(2.dp, Color.White.copy(alpha = 0.28f), CircleShape)
                    .hoverable(interaction)
                    .clickable(interactionSource = interaction, indication = null, enabled = enabled) {
                        showWidget = true
                    },
                contentAlignment = Alignment.Center,
            ) {
                if (loading) {
                    CircularProgressIndicator(
                        strokeWidth = 2.dp, color = Color.White,
                        modifier = Modifier.size(d.icon),
                    )
                } else {
                    // Force white rendering regardless of the PNG's
                    // ink colour so the glyph always matches the wordmark.
                    Image(
                        painter = painterResource("tpid_icon.png"),
                        contentDescription = "Sign in with TOKEN PAY ID",
                        modifier = Modifier.size(d.icon),
                        colorFilter = ColorFilter.tint(Color.White),
                    )
                }
            }
        }
    }

    if (showWidget) {
        TpidWidgetDialog(onResult = { r ->
            showWidget = false
            onResult(r)
        })
    }
}
