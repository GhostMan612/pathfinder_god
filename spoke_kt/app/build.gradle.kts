// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================
plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.ksp)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kotlin.serialization)
}

android {
    namespace = "com.pathfindergod.spoke"
    compileSdk = libs.versions.compileSdk.get().toInt()

    defaultConfig {
        applicationId = "com.pathfindergod.spoke"
        minSdk = libs.versions.minSdk.get().toInt()
        targetSdk = libs.versions.targetSdk.get().toInt()
        versionCode = 1
        versionName = "0.1.0"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }

    splits {
        abi {
            isEnable = true
            reset()
            include("armeabi-v7a", "arm64-v8a", "x86", "x86_64")
            isUniversalApk = true
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    buildFeatures {
        compose = true
    }
}

kotlin {
    jvmToolchain(libs.versions.jvmToolchain.get().toInt())
}

dependencies {
    implementation(platform(libs.androidx.compose.bom))
    androidTestImplementation(platform(libs.androidx.compose.bom))

    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.appcompat)
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.ui.graphics)
    implementation(libs.androidx.compose.ui.tooling.preview)
    implementation(libs.androidx.compose.material3)
    implementation(libs.androidx.compose.animation)
    implementation(libs.androidx.compose.material.icons.extended)

    implementation(libs.androidx.lifecycle.viewmodel)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.navigation.compose)
    implementation(libs.androidx.compose.material3.adaptive.navigation.suite)
    implementation(libs.kotlinx.coroutines.android)
    implementation(libs.kotlinx.serialization.json)

    implementation(libs.androidx.room.runtime)
    implementation(libs.androidx.room.ktx)
    ksp(libs.androidx.room.compiler)
    implementation(libs.nga.sqlite.android)

    implementation(libs.filament.android)
    implementation(libs.filamat.android)

    implementation(libs.retrofit)
    implementation(libs.retrofit.serialization)
    implementation(libs.okhttp)

    // AGDK's POM pins androidx.tracing:tracing with a hard range that Gradle imports as
    // {strictly 1.0.0}. androidx.test:monitor 1.7.x (which Compose's EspressoLink drives)
    // calls Trace.forceEnableAppTracing(), added in tracing 1.1.0, and the app APK's dex
    // takes precedence over the test APK's - so the call died with NoSuchMethodError inside
    // AndroidComposeUiTestEnvironment.runTest, killing the test environment before it could
    // register the Compose root. That surfaced as all 37 instrumented tests failing with
    // "No compose hierarchies found in the app". Upstream: android-test #2246, #2248.
    //
    // The dependency has to be excluded rather than merely upgraded: a stricter declaration
    // elsewhere in the graph would otherwise win, because androidx.test declares tracing only
    // for the test scope while the poisoned copy lives in the app scope.
    implementation(libs.agdk.games.activity) {
        exclude(group = "androidx.tracing", module = "tracing")
    }
    implementation(libs.agdk.games.frame.pacing) {
        exclude(group = "androidx.tracing", module = "tracing")
    }
    implementation(libs.androidx.tracing)

    debugImplementation(libs.androidx.compose.ui.tooling)
    // NOTE: androidx.compose.ui:ui-test-manifest is deliberately NOT a dependency. It exists
    // only to contribute androidx.activity.ComponentActivity to the manifest so that
    // createComposeRule() can resolve a host implicitly. Per the official docs it is "needed
    // for createComposeRule(), but not for createAndroidComposeRule<YourActivity>()", which
    // instead requires the activity to be declared in the app's own manifest. Every test here
    // uses createAndroidComposeRule<ComposeTestActivity>(), with ComposeTestActivity declared
    // in src/debug/AndroidManifest.xml, so the implicit manifest contribution is not needed.

    testImplementation(libs.junit)

    androidTestImplementation(libs.junit)
    androidTestImplementation(libs.androidx.test.core.ktx)
    androidTestImplementation(libs.androidx.test.ext.junit)
    androidTestImplementation(libs.androidx.test.runner)
    androidTestImplementation(libs.androidx.compose.ui.test.junit4)
}
