plugins {
    kotlin("jvm")
    kotlin("plugin.serialization")
    id("org.jetbrains.compose")
    // NOTE: do NOT add `id("org.jetbrains.kotlin.plugin.compose")` here —
    // that plugin only exists on Kotlin 2.x. With Kotlin 1.9 the Compose
    // compiler still ships inside `org.jetbrains.compose` and the extra
    // id aborts configure with "Plugin was not found in any of …".
    `maven-publish`
}

group = "space.tokenpay.id"
version = "3.0.1"

kotlin {
    // Kotlin 1.9 + Compose 1.6 runs on JDK 17 LTS. Higher toolchain versions
    // were only needed when the Compose compiler plugin (Kotlin 2.x) came in.
    jvmToolchain(17)
}

dependencies {
    implementation(compose.desktop.currentOs)
    implementation(compose.material3)
    implementation(compose.materialIconsExtended)

    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.8.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-swing:1.8.0")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.6.3")

    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("com.squareup.okhttp3:logging-interceptor:4.12.0")

    // JNA — Windows DPAPI / macOS Keychain / Linux libsecret native bindings
    implementation("net.java.dev.jna:jna:5.14.0")
    implementation("net.java.dev.jna:jna-platform:5.14.0")

    // ZXing — QR code generation for the in-widget QR login flow.
    // Pure-Java, ~540 KB; no native/AWT-only deps.
    implementation("com.google.zxing:core:3.5.3")

    testImplementation(kotlin("test"))
    testImplementation("org.junit.jupiter:junit-jupiter:5.10.2")
}

tasks.test {
    useJUnitPlatform()
}

publishing {
    publications {
        create<MavenPublication>("maven") {
            from(components["java"])
            artifactId = "tokenpay-id-jvm"
        }
    }
}
