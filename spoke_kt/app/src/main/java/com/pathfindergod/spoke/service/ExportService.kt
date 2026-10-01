// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.service

import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import android.util.Base64
import androidx.core.content.FileProvider
import com.pathfindergod.spoke.data.local.CharacterEntity
import java.io.File
import java.io.FileOutputStream
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

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

    fun shareMapImage(context: Context, base64Png: String, fileName: String) {
        val appContext = context.applicationContext
        val safe = fileName.take(48).ifBlank { "map" }
        exportScope.launch {
            val uri = writeMap(appContext, base64Png, safe) ?: return@launch
            withContext(Dispatchers.Main) { sendImage(appContext, uri, safe) }
        }
    }

    private suspend fun writeMap(
        context: Context,
        base64Png: String,
        safe: String,
    ): Uri? = withContext(Dispatchers.IO) {
        try {
            val raw = Base64.decode(base64Png, Base64.DEFAULT)
            val bitmap = BitmapFactory.decodeByteArray(raw, 0, raw.size) ?: return@withContext null
            val dir = File(context.cacheDir, "exports").apply { mkdirs() }
            val file = File(dir, "$safe.png")
            FileOutputStream(file).use { out ->
                bitmap.compress(Bitmap.CompressFormat.PNG, 100, out)
            }
            bitmap.recycle()
            FileProvider.getUriForFile(context, AUTHORITY, file)
        } catch (_: Exception) {
            null
        }
    }

    private fun sendImage(context: Context, uri: Uri, title: String) {
        try {
            val intent = Intent(Intent.ACTION_SEND)
                .setType("image/png")
                .putExtra(Intent.EXTRA_STREAM, uri)
                .addFlags(
                    Intent.FLAG_GRANT_READ_URI_PERMISSION or
                        Intent.FLAG_ACTIVITY_NEW_TASK,
                )
            context.startActivity(Intent.createChooser(intent, title))
        } catch (_: Exception) {
            Unit
        }
    }

    private val exportScope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
}
