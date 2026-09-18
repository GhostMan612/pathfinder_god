// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.service

import android.content.Context
import android.content.Intent
import android.graphics.BitmapFactory
import android.util.Base64
import androidx.core.content.FileProvider
import com.pathfindergod.spoke.data.local.CharacterEntity
import java.io.File
import java.io.FileOutputStream

object ExportService {
    const val AUTHORITY = "com.pathfindergod.spoke.fileprovider"

    fun shareCharacter(context: Context, entity: CharacterEntity) {
        val text = buildString {
            appendLine("# ${entity.name}")
            appendLine()
            appendLine(
                "${entity.ancestry ?: "—"} · " +
                    "${entity.characterClass ?: "—"} · Level ${entity.level}",
            )
            if (!entity.speed.isNullOrBlank()) appendLine("Speed: ${entity.speed}")
            if (!entity.notes.isNullOrBlank()) {
                appendLine()
                appendLine(entity.notes)
            }
        }
        val intent = Intent(Intent.ACTION_SEND)
            .setType("text/plain")
            .putExtra(Intent.EXTRA_SUBJECT, entity.name)
            .putExtra(Intent.EXTRA_TEXT, text)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        context.startActivity(Intent.createChooser(intent, entity.name))
    }

    fun shareMapImage(context: Context, base64Png: String, fileName: String): Boolean {
        return try {
            val raw = Base64.decode(base64Png, Base64.DEFAULT)
            val bitmap = BitmapFactory.decodeByteArray(raw, 0, raw.size)
                ?: return false
            val dir = File(context.cacheDir, "exports").apply { mkdirs() }
            val safe = fileName.take(48).ifBlank { "map" }
            val file = File(dir, "$safe.png")
            FileOutputStream(file).use { out ->
                bitmap.compress(android.graphics.Bitmap.CompressFormat.PNG, 100, out)
            }
            val uri = FileProvider.getUriForFile(context, AUTHORITY, file)
            val intent = Intent(Intent.ACTION_SEND)
                .setType("image/png")
                .putExtra(Intent.EXTRA_STREAM, uri)
                .addFlags(
                    Intent.FLAG_GRANT_READ_URI_PERMISSION or
                        Intent.FLAG_ACTIVITY_NEW_TASK,
                )
            context.startActivity(Intent.createChooser(intent, safe))
            true
        } catch (_: Exception) {
            false
        }
    }
}
