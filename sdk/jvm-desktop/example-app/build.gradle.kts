plugins {
    kotlin("jvm")
    id("org.jetbrains.compose")
    // No `application` plugin here — the Compose plugin already registers a
    // `run` task via its own `application { … }` block in `compose.desktop`
    // below. Having both aborts configure with
    // "Cannot add task 'run' as a task with that name already exists".
}

group = "space.tokenpay.examples"
version = "1.0.0"

kotlin { jvmToolchain(17) }

dependencies {
    implementation(project(":tokenpay-id-jvm"))
    implementation(compose.desktop.currentOs)
    implementation(compose.material3)
}

compose.desktop {
    application {
        mainClass = "space.tokenpay.examples.MainKt"
        nativeDistributions {
            targetFormats(org.jetbrains.compose.desktop.application.dsl.TargetFormat.Msi,
                          org.jetbrains.compose.desktop.application.dsl.TargetFormat.Dmg,
                          org.jetbrains.compose.desktop.application.dsl.TargetFormat.Deb)
            packageName = "TpidExample"
            packageVersion = "1.0.0"
        }
    }
}
