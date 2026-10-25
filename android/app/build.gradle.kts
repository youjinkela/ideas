plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.kapt")
}
android {
    namespace = "com.ideaecho.app"
    compileSdk = 36
    defaultConfig {
        applicationId = "com.ideaecho.app"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "0.1.0"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        manifestPlaceholders["appLabel"] = "点子回声"
        javaCompileOptions { annotationProcessorOptions { arguments["room.schemaLocation"] = "$projectDir/schemas" } }
    }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
    kotlinOptions { jvmTarget = "17" }
    buildFeatures { viewBinding = true; buildConfig = true }
    testBuildType = providers.gradleProperty("instrumentationBuildType").getOrElse("debug")
    buildTypes {
        debug { manifestPlaceholders["allowCleartext"] = "true" }
        release { manifestPlaceholders["allowCleartext"] = "false"; isMinifyEnabled = false }
        create("acceptance") {
            initWith(getByName("debug"))
            applicationIdSuffix = ".acceptance"
            versionNameSuffix = "-acceptance"
            manifestPlaceholders["appLabel"] = "点子回声·后台验收"
            matchingFallbacks += listOf("debug")
        }
    }
}
dependencies {
    implementation("androidx.activity:activity-ktx:1.10.1")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.9.1")
    implementation("androidx.room:room-runtime:2.8.5")
    implementation("androidx.room:room-ktx:2.8.5")
    kapt("androidx.room:room-compiler:2.8.5")
    implementation("androidx.work:work-runtime-ktx:2.11.2")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.10.2")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.json:json:20250517")
    androidTestImplementation("androidx.test:runner:1.6.2")
    androidTestImplementation("androidx.test.ext:junit:1.2.1")
    androidTestImplementation("androidx.room:room-testing:2.8.5")
    androidTestImplementation("com.squareup.okhttp3:mockwebserver:4.12.0")
}
