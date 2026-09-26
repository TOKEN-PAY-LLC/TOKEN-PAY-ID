package space.tokenpay.id.example

import android.app.Application
import space.tokenpay.id.TpidAuth
import space.tokenpay.id.TpidConfig

class ExampleApp : Application() {
    override fun onCreate() {
        super.onCreate()
        TpidAuth.initialize(
            context = this,
            config = TpidConfig(
                clientId = "tpid_pk_example_REPLACE_ME",
                redirectUri = "space.tokenpay.id.example:/auth/callback",
                scopes = listOf("openid", "profile", "email"),
                theme = TpidConfig.Theme.AUTO,
            )
        )
    }
}
