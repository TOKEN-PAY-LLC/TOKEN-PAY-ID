plugins {
    id("com.android.library") version "8.2.2" apply false
    id("com.android.application") version "8.2.2" apply false
    id("org.jetbrains.kotlin.android") version "1.9.22" apply false
    id("org.jetbrains.kotlin.plugin.serialization") version "1.9.22" apply false
    // NOTE: the `org.jetbrains.kotlin.plugin.compose` plugin only exists
    // for Kotlin 2.0+. While we are on Kotlin 1.9.22 we configure Compose
    // through `android { composeOptions { kotlinCompilerExtensionVersion } }`
    // inside :tokenpay-id-sdk instead.
}

tasks.register("clean", Delete::class) {
    delete(rootProject.layout.buildDirectory)
}
