plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

private fun buildConfigString(value: String): String =
    "\"${value.filter { it.isLetterOrDigit() || it in ":-_" }}\""

private fun firebaseSetting(name: String): String =
    providers.gradleProperty(name)
        .orElse(providers.environmentVariable(name))
        .getOrElse("")

android {
    namespace = "com.example.kharazmiadmin"
    compileSdk = 34 // نسخه پایدار اندروید 14

    defaultConfig {
        applicationId = "com.example.kharazmiadmin"
        minSdk = 24
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        buildConfigField("String", "FIREBASE_API_KEY", buildConfigString(firebaseSetting("FIREBASE_API_KEY")))
        buildConfigField("String", "FIREBASE_APP_ID", buildConfigString(firebaseSetting("FIREBASE_APP_ID")))
        buildConfigField("String", "FIREBASE_PROJECT_ID", buildConfigString(firebaseSetting("FIREBASE_PROJECT_ID")))
        buildConfigField("String", "FIREBASE_MESSAGING_SENDER_ID", buildConfigString(firebaseSetting("FIREBASE_MESSAGING_SENDER_ID")))
    }

    buildFeatures {
        buildConfig = true
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_1_8
        targetCompatibility = JavaVersion.VERSION_1_8
    }
    kotlinOptions {
        jvmTarget = "1.8"
    }
}

dependencies {
    // --- هسته و کاتلین (نسخه‌های پایدار و هماهنگ با SDK 34) ---
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("com.google.android.material:material:1.12.0")

    // نسخه 1.9.0 کاملاً با SDK 34 سازگار است (نسخه 1.12 ارور میدهد)
    implementation("androidx.activity:activity-ktx:1.9.0")

    implementation("androidx.constraintlayout:constraintlayout:2.1.4")
    implementation("androidx.gridlayout:gridlayout:1.0.0")
    implementation("androidx.swiperefreshlayout:swiperefreshlayout:1.1.0")

    // --- شبکه (Retrofit) ---
    implementation("com.squareup.retrofit2:retrofit:2.9.0")
    implementation("com.squareup.retrofit2:converter-gson:2.9.0")
    // FCM client; Firebase project values are optional at build time and supplied outside Git.
    implementation("com.google.firebase:firebase-messaging:24.1.0")

    // --- مدیریت تردها (Coroutines) ---
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.7.3")
    // FIX: Bug 19 - explicit lifecycle-owned coroutine support.
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.0")

    // --- بازتاب (Reflect) ---
    implementation("org.jetbrains.kotlin:kotlin-reflect:1.9.24")

    // --- امنیت (Biometric) ---
    implementation("androidx.biometric:biometric:1.1.0")
    // FIX: Android credential leftover - Keystore-backed encrypted remembered passwords.
    implementation("androidx.security:security-crypto:1.1.0")

    // --- تقویم فارسی ---
    implementation("com.github.aliab:Persian-Date-Picker-Dialog:1.8.0")

    // --- نمودارها ---
    implementation("com.github.PhilJay:MPAndroidChart:v3.1.0")

    // --- لود تصویر (Glide) ---
    implementation("com.github.bumptech.glide:glide:4.16.0")

    // --- افکت شیمر (Shimmer) ---
    implementation("com.facebook.shimmer:shimmer:0.5.0")

    // --- تست ---
    testImplementation("junit:junit:4.13.2")
    // FIX: Bug 21 - deterministic virtual-time tests for cancellation and search debounce.
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.7.3")
    androidTestImplementation("androidx.test.ext:junit:1.2.1")
    androidTestImplementation("androidx.test.espresso:espresso-core:3.6.1")
}
