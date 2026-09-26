-keep class space.tokenpay.id.** { *; }
-keepclassmembers class space.tokenpay.id.** {
    @kotlinx.serialization.Serializable *;
}
-keep,includedescriptorclasses class space.tokenpay.id.**$$serializer { *; }
