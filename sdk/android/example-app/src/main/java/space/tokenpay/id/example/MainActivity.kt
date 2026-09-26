package space.tokenpay.id.example

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import space.tokenpay.id.TpidLoginButton
import space.tokenpay.id.TpidResult

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                var lastResult by remember { mutableStateOf<String>("Not signed in") }
                Surface(Modifier.fillMaxSize()) {
                    Column(
                        Modifier.fillMaxSize().padding(24.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.Center,
                    ) {
                        Text("TOKEN PAY ID Example", fontSize = 24.sp)
                        Spacer(Modifier.height(24.dp))
                        TpidLoginButton { result ->
                            lastResult = when (result) {
                                is TpidResult.Success ->
                                    "Signed in as ${result.user.email}"
                                is TpidResult.Cancelled -> "User cancelled"
                                is TpidResult.Failure   -> "Failed: ${result.error.code} — ${result.error.message}"
                            }
                        }
                        Spacer(Modifier.height(32.dp))
                        Text(lastResult, fontSize = 14.sp)
                    }
                }
            }
        }
    }
}
