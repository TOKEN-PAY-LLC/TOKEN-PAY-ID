// Root build for TOKEN PAY ID JVM Desktop SDK.
// Every plugin the submodules apply without a version MUST be declared here
// at least once with a pinned version + apply false, otherwise Gradle won't
// resolve the coordinates and `:tokenpay-id-jvm` fails to configure.
plugins {
    kotlin("jvm") version "1.9.22" apply false
    kotlin("plugin.serialization") version "1.9.22" apply false
    id("org.jetbrains.compose") version "1.6.10" apply false
}

allprojects {
    repositories {
        mavenCentral()
        // Compose's artifacts (ui-desktop, material3-desktop, …) pull a few
        // `androidx.*` POMs at test-runtime resolution. They only live on
        // Google's Maven, so without this repo `:test` fails with
        // "Could not find androidx.collection:collection:1.4.0".
        google()
        maven("https://maven.pkg.jetbrains.space/public/p/compose/dev")
    }
}
