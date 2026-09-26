-keep class space.tokenpay.id.** { *; }
-keepclassmembers class space.tokenpay.id.** {
    @kotlinx.serialization.Serializable *;
}
-keep,includedescriptorclasses class space.tokenpay.id.**$$serializer { *; }

# OkHttp — platform-specific suppressions
-dontwarn okhttp3.internal.platform.**
-dontwarn org.conscrypt.**
-dontwarn org.bouncycastle.**
-dontwarn org.openjsse.**
