// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.map

import android.graphics.BitmapFactory
import android.util.Base64
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

const val THUMBNAIL_PX = 512
const val VIEWER_PX = 2048

object MapImageDecoder {
    suspend fun decode(base64Png: String, maxDimension: Int): ImageBitmap? =
        withContext(Dispatchers.IO) { decodeNow(base64Png, maxDimension) }

    private fun decodeNow(base64Png: String, maxDimension: Int): ImageBitmap? = try {
        val bytes = Base64.decode(base64Png, Base64.DEFAULT)
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeByteArray(bytes, 0, bytes.size, bounds)
        val options = BitmapFactory.Options().apply {
            inSampleSize = mapSampleSize(bounds.outWidth, bounds.outHeight, maxDimension)
        }
        BitmapFactory.decodeByteArray(bytes, 0, bytes.size, options)?.asImageBitmap()
    } catch (_: Exception) {
        null
    }
}
