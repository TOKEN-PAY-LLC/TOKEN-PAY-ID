package space.tokenpay.id

import android.app.Activity
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.foundation.BorderStroke
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch

/**
 * TOKEN PAY ID login button. Three variants match the official design system:
 *
 * - [TpidButtonVariant.Dark]  — black pill, white "TOKEN PAY ID" wordmark.
 * - [TpidButtonVariant.Light] — white pill with border, black wordmark.
 * - [TpidButtonVariant.IconOnly] — circular button with the brand glyph.
 *
 * The button *only* shows the official logo — no custom label — so every
 * integration across apps and websites looks identical.
 */
@Composable
fun TpidLoginButton(
    modifier: Modifier = Modifier,
    variant: TpidButtonVariant = TpidButtonVariant.Dark,
    size: TpidButtonSize = TpidButtonSize.Medium,
    loading: Boolean = false,
    fullWidth: Boolean = false,
    onResult: (TpidResult) -> Unit,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var inFlight by remember { mutableStateOf(false) }
    val activity = remember(context) {
        var c = context
        while (c is android.content.ContextWrapper && c !is Activity) c = c.baseContext
        c as? Activity
    }
    val enabled = !loading && !inFlight && activity != null

    val onClick: () -> Unit = click@{
        val act = activity ?: return@click
        inFlight = true
        scope.launch {
            val r = runCatching { TpidWidget.present(act) }
                .getOrElse { TpidResult.Failure(TpidError.Unknown(it)) }
            inFlight = false
            onResult(r)
        }
    }
    val dims = size.dims()

    // Shared hover/press interaction source drives the same scale + elevation
    // animation across all three variants so they feel identical in hand.
    val interaction = remember { MutableInteractionSource() }
    val hovered by interaction.collectIsHoveredAsState()
    val pressed by interaction.collectIsPressedAsState()
    val scale by animateFloatAsState(
        targetValue = if (pressed) 0.965f else if (hovered) 1.015f else 1.0f,
        animationSpec = spring(dampingRatio = 0.6f, stiffness = 520f),
        label = "tpid-btn-scale",
    )

    when (variant) {
        TpidButtonVariant.Dark, TpidButtonVariant.Light -> {
            val dark = variant == TpidButtonVariant.Dark
            val bg = if (dark) Color(0xFF0B0B0D) else Color.White
            val fg = if (dark) Color.White else Color(0xFF0B0B0D)
            // Equal-weight border on both themes — fixes the user's "чёрная и
            // белая кнопки пока не очень классные" feedback where the white
            // pill looked outlined and the black one looked bare.
            // Pronounced outline — 2dp × 28% alpha reads as a clear ring
            // on both themes. Previously 1.5dp × 18% alpha, which the user
            // said "не хватает окантовки" on the DARK pill.
            val borderCol = if (dark) Color.White.copy(alpha = 0.28f)
                            else Color(0xFF0B0B0D).copy(alpha = 0.28f)
            val wmRes = if (dark) R.drawable.tpid_wordmark_white else R.drawable.tpid_wordmark_black
            val shape = RoundedCornerShape(dims.corner)
            val shadowAlpha = if (dark) 0.5f else 0.18f
            Row(
                modifier = modifier
                    .then(if (fullWidth) Modifier.fillMaxWidth() else Modifier)
                    .heightIn(min = dims.height)
                    .scale(scale)
                    .shadow(
                        elevation = if (hovered) 10.dp else 4.dp,
                        shape = shape,
                        clip = false,
                        ambientColor = Color.Black.copy(alpha = shadowAlpha),
                        spotColor = Color.Black.copy(alpha = shadowAlpha),
                    )
                    .clip(shape)
                    .background(bg)
                    .border(BorderStroke(2.dp, borderCol), shape)
                    .hoverable(interaction)
                    .clickable(
                        interactionSource = interaction,
                        indication = null,
                        enabled = enabled,
                        onClick = onClick,
                    )
                    .padding(horizontal = dims.padH, vertical = dims.padV),
                horizontalArrangement = Arrangement.Center,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                if (inFlight) {
                    CircularProgressIndicator(
                        strokeWidth = 2.dp, color = fg,
                        modifier = Modifier.size(dims.wordmark),
                    )
                } else {
                    Image(
                        painter = painterResource(id = wmRes),
                        contentDescription = "Sign in with TOKEN PAY ID",
                        modifier = Modifier.height(dims.wordmark),
                    )
                }
            }
        }
        TpidButtonVariant.IconOnly -> {
            // Circular black button with the brand glyph painted white so it
            // matches the saturn logo used in the tokenpay.space hero and
            // the wordmark on the DARK pill.
            Box(
                modifier = modifier
                    .size(dims.height)
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
                    .border(BorderStroke(2.dp, Color.White.copy(alpha = 0.28f)), CircleShape)
                    .hoverable(interaction)
                    .clickable(
                        interactionSource = interaction,
                        indication = null,
                        enabled = enabled,
                        onClick = onClick,
                    ),
                contentAlignment = Alignment.Center,
            ) {
                if (inFlight) {
                    CircularProgressIndicator(
                        strokeWidth = 2.dp, color = Color.White,
                        modifier = Modifier.size(dims.icon),
                    )
                } else {
                    Image(
                        painter = painterResource(id = R.drawable.tpid_icon),
                        contentDescription = "Sign in with TOKEN PAY ID",
                        modifier = Modifier.size(dims.icon),
                        colorFilter = ColorFilter.tint(Color.White),
                    )
                }
            }
        }
    }
}

enum class TpidButtonVariant { Dark, Light, IconOnly }

enum class TpidButtonSize { Small, Medium, Large }

/**
 * [wordmark] — height of the wordmark image on DARK / LIGHT variants.
 * [icon]     — size of the single-glyph icon on ICON_ONLY.
 */
private data class Dims(
    val height: Dp, val wordmark: Dp, val icon: Dp,
    val padH: Dp, val padV: Dp, val corner: Dp,
)

private fun TpidButtonSize.dims(): Dims = when (this) {
    // Wordmark sized 18/22/26 dp on Small/Medium/Large after a second round
    // of user feedback ("чтобы лого был немного крупнее"). The pill heights
    // and horizontal padding grow a touch so the logo still has breathing
    // room inside the rounded capsule.
    TpidButtonSize.Small  -> Dims(40.dp, 18.dp, 22.dp, 20.dp, 9.dp, 999.dp)
    TpidButtonSize.Medium -> Dims(48.dp, 22.dp, 28.dp, 26.dp, 11.dp, 999.dp)
    TpidButtonSize.Large  -> Dims(56.dp, 26.dp, 34.dp, 32.dp, 13.dp, 999.dp)
}
