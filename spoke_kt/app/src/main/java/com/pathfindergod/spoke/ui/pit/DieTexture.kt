// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.pit

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.Path
import android.graphics.Typeface

class AtlasLevel(
    val width: Int,
    val height: Int,
    val rgba: ByteArray,
) {
    val bytes: Int get() = rgba.size
}

object DieTexture {

    private const val PARCHMENT_A = 0xFFE8DCC0.toInt()
    private const val PARCHMENT_B = 0xFFDCCFAE.toInt()
    private const val INK = 0xFF2B2118.toInt()
    private const val GOLD = 0xFFC8A846.toInt()

    fun baseColorLevels(mesh: DieMesh): List<AtlasLevel> = pyramid(
        drawBaseColor(mesh),
        mesh.cols * DieAtlas.TILE,
        mesh.rows * DieAtlas.TILE,
        true,
    )

    fun normalLevels(mesh: DieMesh): List<AtlasLevel> = pyramid(
        DieAtlas.bevelNormals(mesh.faceCount, mesh.faceKinds, atlasGrid(mesh)),
        mesh.cols * DieAtlas.TILE,
        mesh.rows * DieAtlas.TILE,
        false,
    )

    fun feltLevels(): List<AtlasLevel> = pyramid(
        DieAtlas.feltPixels(PitRenderConfig.FELT_SIZE),
        PitRenderConfig.FELT_SIZE,
        PitRenderConfig.FELT_SIZE,
        true,
    )

    fun shadowLevels(): List<AtlasLevel> = pyramid(
        DieAtlas.contactShadowPixels(PitRenderConfig.SHADOW_SIZE),
        PitRenderConfig.SHADOW_SIZE,
        PitRenderConfig.SHADOW_SIZE,
        false,
    )

    fun atlasGrid(mesh: DieMesh): DieAtlasGrid =
        DieAtlasGrid(mesh.cols, mesh.rows, DieAtlas.TILE)

    fun drawBaseColor(mesh: DieMesh): IntArray {
        val grid = atlasGrid(mesh)
        val tile = grid.tile
        val bitmap = Bitmap.createBitmap(grid.width, grid.height, Bitmap.Config.ARGB_8888)
        val pixels = IntArray(grid.width * grid.height)
        try {
            val canvas = Canvas(bitmap)
            canvas.drawColor(PARCHMENT_A)
            val fill = Paint().apply {
                style = Paint.Style.FILL
                isAntiAlias = false
            }
            val edge = Paint().apply {
                style = Paint.Style.STROKE
                strokeWidth = tile * 0.0175f
                isAntiAlias = true
                color = GOLD
            }
            val glyph = Paint().apply {
                color = INK
                textSize = tile * 0.42f
                textAlign = Paint.Align.CENTER
                isAntiAlias = true
                typeface = Typeface.create(Typeface.SERIF, Typeface.BOLD)
            }
            for (face in 0 until mesh.faceCount) {
                val cell = grid.tileOf(face)
                val left = cell.left.toFloat()
                val top = cell.top.toFloat()
                fill.color = if (face % 2 == 0) PARCHMENT_A else PARCHMENT_B
                canvas.drawRect(left, top, left + tile, top + tile, fill)
                val kind = mesh.faceKinds[face]
                val corners = DieAtlas.cornerCount(kind)
                val path = Path()
                for (corner in 0 until corners) {
                    val (fx, fy) = DieMeshBuilder.tileCorner(kind, corner)
                    val x = left + fx * tile
                    val y = top + fy * tile
                    if (corner == 0) path.moveTo(x, y) else path.lineTo(x, y)
                }
                path.close()
                canvas.drawPath(path, edge)
                canvas.drawText(
                    "${mesh.faceNumbers[face]}",
                    left + tile / 2f,
                    top + tile / 2f + tile * 0.15f,
                    glyph,
                )
            }
            bitmap.getPixels(pixels, 0, grid.width, 0, 0, grid.width, grid.height)
        } finally {
            bitmap.recycle()
        }
        return pixels
    }

    private fun pyramid(
        base: IntArray,
        width: Int,
        height: Int,
        keepAlpha: Boolean,
    ): List<AtlasLevel> {
        val levels = ArrayList<AtlasLevel>(DieAtlas.levelCount(width, height))
        var w = width
        var h = height
        var pixels = base
        while (true) {
            levels.add(AtlasLevel(w, h, DieAtlas.toRgbaA(pixels, keepAlpha)))
            if (w == 1 && h == 1) break
            pixels = DieAtlas.downsample(pixels, w, h)
            w = maxOf(1, w shr 1)
            h = maxOf(1, h shr 1)
        }
        return levels
    }
}
