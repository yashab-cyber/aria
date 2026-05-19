/*
  BUILD WITHOUT ANDROID STUDIO:
  
  1. Install JDK 17:
     Linux:   sudo apt install openjdk-17-jdk
     Windows: winget install EclipseAdoptium.Temurin.17.JDK
  
  2. Download Android Command Line Tools only (no Android Studio):
     https://developer.android.com/studio#command-line-tools-only
     Extract to ~/android-sdk/cmdline-tools/latest/
  
  3. Set environment:
     export ANDROID_HOME=~/android-sdk
     export PATH=$PATH:$ANDROID_HOME/cmdline-tools/latest/bin
  
  4. Install SDK packages:
     sdkmanager --licenses
     sdkmanager "platform-tools" "platforms;android-34" "build-tools;34.0.0"
  
  5. Update local.properties with your sdk.dir path
  
  6. Generate keystore (one time):
     keytool -genkey -v -keystore aria-debug.keystore -alias aria \
       -keyalg RSA -keysize 2048 -validity 10000 \
       -storepass android -keypass android \
       -dname "CN=ARIA,OU=Dev,O=ARIA,L=X,ST=X,C=US"
  
  7. Build:
     chmod +x gradlew
     ./gradlew assembleDebug
  
  8. APK location:
     app/build/outputs/apk/debug/app-debug.apk
  
  9. Install:
     adb install app/build/outputs/apk/debug/app-debug.apk
     OR copy APK to phone and install manually
  
  10. Enable service on phone:
      Settings -> Accessibility -> ARIA Agent -> Enable
*/

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.aria.agent"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.aria.agent"
        minSdk = 26
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"
    }

    signingConfigs {
        getByName("debug") {
            storeFile = file("aria-debug.keystore")
            storePassword = "android"
            keyAlias = "aria"
            keyPassword = "android"
        }
    }

    buildTypes {
        getByName("debug") {
            signingConfig = signingConfigs.getByName("debug")
            isDebuggable = true
        }
        getByName("release") {
            signingConfig = signingConfigs.getByName("debug")
            isMinifyEnabled = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
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
        buildConfig = true
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.12.0")
    implementation("androidx.appcompat:appcompat:1.6.1")
    implementation("com.google.android.material:material:1.11.0")
    implementation("androidx.constraintlayout:constraintlayout:2.1.4")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3")
    implementation("com.google.code.gson:gson:2.10.1")
    implementation("androidx.work:work-runtime-ktx:2.9.0")
    implementation("androidx.security:security-crypto:1.1.0-alpha06")
    implementation("androidx.lifecycle:lifecycle-service:2.7.0")
}

configurations.all {
    resolutionStrategy {
        force("org.jetbrains.kotlin:kotlin-stdlib:1.9.22")
        force("org.jetbrains.kotlin:kotlin-stdlib-jdk8:1.9.22")
    }
}
