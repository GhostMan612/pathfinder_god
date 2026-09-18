// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.local

import android.content.Context
import java.io.File
import java.io.FileOutputStream
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

object DatabaseAssetManager {
    const val ASSET_PATH = "rules/pathfinder_rag.db"
    const val BUNDLE_VERSION = 2

    suspend fun ensureExtracted(context: Context): File =
        withContext(Dispatchers.IO) {
            val out = context.getDatabasePath(RulesDatabase.FILE_NAME)
            val marker = File(out.parent, "${RulesDatabase.FILE_NAME}.v$BUNDLE_VERSION")
            if (out.exists() && marker.exists()) {
                return@withContext out
            }
            out.parentFile?.mkdirs()
            val tmp = File.createTempFile("rules", ".db", out.parentFile)
            try {
                context.assets.open(ASSET_PATH).use { raw ->
                    FileOutputStream(tmp).use { dst ->
                        raw.copyTo(dst)
                    }
                }
                if (!tmp.renameTo(out)) {
                    tmp.copyTo(out, overwrite = true)
                    tmp.delete()
                }
                marker.createNewFile()
            } catch (e: Exception) {
                tmp.delete()
                throw e
            }
            out
        }
}
