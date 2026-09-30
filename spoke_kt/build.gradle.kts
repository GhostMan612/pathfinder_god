// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================
plugins {
    alias(libs.plugins.android.application) apply false
    alias(libs.plugins.ksp) apply false
    alias(libs.plugins.kotlin.compose) apply false
    alias(libs.plugins.kotlin.serialization) apply false
}

val rulesDb = layout.projectDirectory.file("app/src/main/assets/rules/pathfinder_rag.db")

if (!rulesDb.asFile.exists()) {
    logger.warn(
        "pathfinder_rag.db is absent. The offline rules search will extract nothing " +
            "(RULES.md 5.2). Run: git lfs install && git lfs pull",
    )
} else {
    val magic = rulesDb.asFile.inputStream().use { stream ->
        val head = ByteArray(15)
        val read = stream.read(head)
        String(head, 0, maxOf(read, 0), Charsets.US_ASCII)
    }
    if (!magic.startsWith("SQLite format 3")) {
        throw GradleException(
            "app/src/main/assets/rules/pathfinder_rag.db is a Git LFS pointer, not the real " +
                "58MB extract. This is what a clone without Git LFS produces, and the build " +
                "would otherwise fail later with an unreadable asset.\n" +
                "Fix: git lfs install && git lfs pull\n" +
                "Then: verify with  head -c 15 app/src/main/assets/rules/pathfinder_rag.db  ->  SQLite format 3",
        )
    }
}

val localProps = layout.projectDirectory.file("local.properties").asFile
val sdkFromLocalProps =
    localProps.takeIf { it.exists() }?.readLines()?.firstOrNull { it.trimStart().startsWith("sdk.dir") }
val sdkFromEnv = System.getenv("ANDROID_HOME") ?: System.getenv("ANDROID_SDK_ROOT")
if (sdkFromLocalProps == null && sdkFromEnv == null) {
    logger.warn(
        "Android SDK location not found. A fresh clone has no local.properties (it is " +
            "gitignored), so either ANDROID_HOME or local.properties must supply it.\n" +
            "Fix: echo \"sdk.dir=C:\\\\android\\\\sdk\" > local.properties   (or export ANDROID_HOME)",
    )
}
