package space.tokenpay.examples

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Window
import androidx.compose.ui.window.application
import androidx.compose.ui.window.rememberWindowState
import space.tokenpay.id.jvm.*

fun main() = application {
    // Initialize the SDK once at startup.
    TpidAuth.initialize(TpidConfig(
        clientId = "tpid_pk_demo_your_public_key",
        redirectUri = "space.cupol.vpn:/auth/callback",
        theme = TpidConfig.Theme.AUTO,
    ))

    Window(
        onCloseRequest = ::exitApplication,
        title = "TOKEN PAY ID — Desktop Example",
        state = rememberWindowState(width = 520.dp, height = 400.dp),
    ) {
        MaterialTheme(colorScheme = darkColorScheme()) {
            Surface(color = Color(0xFF0A0A0A), contentColor = Color.White) {
                App()
            }
        }
    }
}

@Composable
private fun App() {
    var user: TpidUser? by remember { mutableStateOf(TpidAuth.currentUser()) }
    var error: String? by remember { mutableStateOf(null) }

    Column(
        modifier = Modifier.fillMaxSize().padding(32.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text("CUPOL VPN — Desktop", fontSize = 20.sp, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(32.dp))

        if (user != null) {
            Text("Hello, ${user!!.name ?: user!!.email}", fontSize = 15.sp)
            Spacer(Modifier.height(12.dp))
            Text(user!!.email, fontSize = 12.sp, color = Color.White.copy(alpha = 0.6f))
            Spacer(Modifier.height(24.dp))
            Button(onClick = { TpidAuth.signOut(); user = null }) {
                Text("Sign out")
            }
        } else {
            TpidLoginButton(
                variant = TpidButtonVariant.DARK,
                fullWidth = true,
            ) { result ->
                when (result) {
                    is TpidResult.Success -> { user = result.user; error = null }
                    is TpidResult.Failure -> error = "${result.error.code}: ${result.error.message}"
                    TpidResult.Cancelled -> {}
                }
            }
            if (error != null) {
                Spacer(Modifier.height(12.dp))
                Text(error!!, color = Color(0xFFD64545), fontSize = 12.sp)
            }
        }
    }
}
