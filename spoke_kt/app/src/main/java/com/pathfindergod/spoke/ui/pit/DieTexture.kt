// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.pit

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.Typeface
import java.nio.ByteBuffer

object DieTexture {
    const val TILE = 400
    const val WIDTH = DieMeshBuilder.COLS * TILE
    const val HEIGHT = DieMeshBuilder.ROWS * TILE

    private const val PARCHMENT_A = 0xFFE8DCC0.toInt()
    private const val PARCHMENT_B = 0xFFDCCFAE.toInt()
    private const val INK = 0xFF2B2118.toInt()
    private const val GOLD = 0xFFC8A846.toInt()

    fun build(numbers: IntArray, kinds: IntArray): Bitmap {
        val bitmap = Bitmap.createBitmap(WIDTH, HEIGHT, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bitmap)
        val fill = Paint().apply { style = Paint.Style.FILL }
        val edge = Paint().apply {
            style = Paint.Style.STROKE
            strokeWidth = 7f
            isAntiAlias = true
            color = GOLD
        }
        val glyph = Paint().apply {
            color = INK
            textSize = 168f
            textAlign = Paint.Align.CENTER
            isAntiAlias = true
            typeface = Typeface.create(Typeface.SERIF, Typeface.BOLD)
        }
        for (face in numbers.indices) {
            val col = face % DieMeshBuilder.COLS
            val row = face / DieMeshBuilder.COLS
            val left = col * TILE.toFloat()
            val top = row * TILE.toFloat()
            fill.color = if (face % 2 == 0) PARCHMENT_A else PARCHMENT_B
            canvas.drawRect(left, top, left + TILE, top + TILE, fill)
            val corners = when (kinds[face]) {
                DieMeshBuilder.QUAD -> 4
                DieMeshBuilder.PENT -> 5
                else -> 3
            }
            val path = android.graphics.Path().apply {
                for (corner in 0 until corners) {
                    val (fx, fy) = DieMeshBuilder.tileCorner(kinds[face], corner)
                    val x = left + fx * TILE
                    val y = top + fy * TILE
                    if (corner == 0) moveTo(x, y) else lineTo(x, y)
                }
                close()
            }
            canvas.drawPath(path, edge)
            canvas.drawText(
                "${numbers[face]}",
                left + TILE / 2f,
                top + TILE / 2f + 60f,
                glyph,
            )
        }
        return bitmap
    }

    fun toRgbaBuffer(bitmap: Bitmap): ByteBuffer {
        val buffer = ByteBuffer.allocateDirect(bitmap.byteCount)
        bitmap.copyPixelsToBuffer(buffer)
        buffer.rewind()
        return buffer
    }
}
