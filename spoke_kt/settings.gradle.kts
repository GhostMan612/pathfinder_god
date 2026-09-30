// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================
pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

// The foojay resolver lets a fresh clone resolve the JDK 17 toolchain that
// app/build.gradle.kts pins, on any machine, without a hand-set JAVA_HOME.
// It replaces the machine-generated gradle/gradle-daemon-jvm.properties pin,
// which is gitignored and untracked (see .gitignore).
plugins {
    id("org.gradle.toolchains.foojay-resolver-convention") version "1.0.0"
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "PathfinderGod"
include(":app")
