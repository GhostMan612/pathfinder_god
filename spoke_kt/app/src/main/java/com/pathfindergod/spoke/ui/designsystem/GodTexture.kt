// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.designsystem

import android.graphics.Bitmap
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.ImageShader
import androidx.compose.ui.graphics.ShaderBrush
import androidx.compose.ui.graphics.TileMode
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.lerp
import androidx.compose.ui.graphics.toArgb
import kotlin.math.floor

object GodTexture {

    const val TILE = 96
    const val GRID = 24

    @Composable
    fun parchmentBrush(): ShaderBrush {
        val tile = remember {
            grainTile(TILE, GRID, 0x50C4, 0x2B2118, 0xF6EED8, 0.05f)
        }
        return remember(tile) { tile.toBrush() }
    }

    @Composable
    fun feltBrush(): ShaderBrush {
        val tile = remember {
            grainTile(TILE, GRID, 0x9E37, 0x0E1116, 0x4A5560, 0.09f)
        }
        return remember(tile) { tile.toBrush() }
    }

    fun grainTile(
        size: Int,
        grid: Int,
        seed: Int,
        dark: Int,
        light: Int,
        maxAlpha: Float,
    ): ImageBitmap {
        val lattice = FloatArray(grid * grid)
        var state = seed or 1
        for (index in lattice.indices) {
            state = state * 1664525 + 1013904223
            lattice[index] = ((state ushr 8) and 0xFFFF) / 65535f
        }
        val shadow = Color(dark)
        val highlight = Color(light)
        val norm = 0.5f + 0.25f + 0.125f
        val pixels = IntArray(size * size)
        for (y in 0 until size) {
            val v = y.toFloat() * grid / size
            for (x in 0 until size) {
                val u = x.toFloat() * grid / size
                val n = (
                    0.5f * latticeAt(lattice, grid, u, v) +
                        0.25f * latticeAt(lattice, grid, u * 2f, v * 2f) +
                        0.125f * latticeAt(lattice, grid, u * 4f, v * 4f)
                    ) / norm
                pixels[y * size + x] = lerp(shadow, highlight, n)
                    .copy(alpha = maxAlpha * (0.35f + 0.65f * n))
                    .toArgb()
            }
        }
        return Bitmap.createBitmap(pixels, size, size, Bitmap.Config.ARGB_8888)
            .asImageBitmap()
    }

    private fun ImageBitmap.toBrush(): ShaderBrush = ShaderBrush(
        ImageShader(this, TileMode.Repeated, TileMode.Repeated),
    )

    private fun latticeAt(
        lattice: FloatArray,
        grid: Int,
        u: Float,
        v: Float,
    ): Float {
        val floorU = floor(u)
        val floorV = floor(v)
        val x0 = floorU.toInt() % grid
        val y0 = floorV.toInt() % grid
        val x1 = (x0 + 1) % grid
        val y1 = (y0 + 1) % grid
        val sx = smooth(u - floorU)
        val sy = smooth(v - floorV)
        val topLeft = lattice[y0 * grid + x0]
        val topRight = lattice[y0 * grid + x1]
        val bottomLeft = lattice[y1 * grid + x0]
        val bottomRight = lattice[y1 * grid + x1]
        val top = topLeft + (topRight - topLeft) * sx
        val bottom = bottomLeft + (bottomRight - bottomLeft) * sx
        return top + (bottom - top) * sy
    }

    private fun smooth(step: Float): Float = step * step * (3f - 2f * step)
}