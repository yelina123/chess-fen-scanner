plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.chessscan.app"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.chessscan.app"
        minSdk = 24
        targetSdk = 34
        versionCode = 22
        versionName = "1.10.0-alpha"
        vectorDrawables { useSupportLibrary = true }
        // 只打 arm64-v8a 原生库(现代手机/鸿蒙均 arm64), APK 从 ~141MB 降到 ~45MB。
        // 准确度不受影响(纯 CPU 剪影算法)。如需支持 32 位旧设备可去掉此过滤。
        ndk { abiFilters += listOf("arm64-v8a") }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        viewBinding = true
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("com.google.android.material:material:1.12.0")
    implementation("androidx.activity:activity-ktx:1.9.0")
    // OpenCV for Android (Maven Central, bundles native libs for all ABIs)
    implementation("org.opencv:opencv:4.10.0")
    // Flutter module (FEN 编辑器, lichess chessground)
    implementation(project(":flutter"))
}
