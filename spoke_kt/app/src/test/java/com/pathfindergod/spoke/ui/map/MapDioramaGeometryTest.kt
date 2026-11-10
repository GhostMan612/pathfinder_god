// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.map

import com.pathfindergod.spoke.data.network.MapFogDto
import com.pathfindergod.spoke.data.network.MapGridDto
import com.pathfindergod.spoke.data.network.MapLightDto
import com.pathfindergod.spoke.data.network.MapPropDto
import com.pathfindergod.spoke.data.network.MapSceneDto
import com.pathfindergod.spoke.data.network.MapZoneDto
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class MapDioramaGeometryTest {

    private fun scene(
        heights: List<List<Int>> = listOf(
            listOf(0, 0, 0, 0),
            listOf(0, 1, 3, 0),
            listOf(0, 1, 1, 0),
        ),
        props: List<MapPropDto> = listOf(
            MapPropDto(type = "crate", x = 1, y = 1, rot = 90),
            MapPropDto(type = "brazier", x = 2, y = 1),
            MapPropDto(type = "crate", x = 99, y = 99),
        ),
        tileM: Float = 1f,
    ) = MapSceneDto(
        grid = MapGridDto(w = 4, h = 3, tileM = tileM),
        heightmap = heights,
        zones = listOf(MapZoneDto(name = "Tavern", biome = "tavern", rect = listOf(1, 1, 2, 1))),
        props = props,
        lights = listOf(MapLightDto(x = 2, y = 1, color = "#ff9a3c", radiusM = 3f)),
        fog = MapFogDto(color = "#0a0d14", density = 0.02f),
    )

    @Test
    fun buildsOnlyNonEmptyTilesAndPlacesProps() {
        val geometry = MapGeometryBuilder.build(scene())
        assertEquals(4, geometry.tileCount)
        assertEquals(2, geometry.propCount)
        assertEquals(3, geometry.maxLevel)
        assertTrue(geometry.batches.any { it.kind == MapSurfaceKind.FLOOR_TAVERN })
        assertTrue(geometry.batches.any { it.kind == MapSurfaceKind.FLOOR_STONE })
        assertTrue(geometry.batches.any { it.kind == MapSurfaceKind.WALL })
        assertTrue(geometry.batches.any { it.kind == MapSurfaceKind.WOOD })
        assertTrue(geometry.batches.any { it.kind == MapSurfaceKind.METAL })
        assertTrue(geometry.batches.any { it.kind == MapSurfaceKind.FLAME })
        assertTrue(geometry.batches.any { it.kind == MapSurfaceKind.GROUND })
    }

    @Test
    fun everyIndexStaysInsideItsVertexBuffer() {
        val geometry = MapGeometryBuilder.build(scene())
        assertTrue(geometry.batches.isNotEmpty())
        for (batch in geometry.batches) {
            assertEquals(batch.vertexCount * 3, batch.positions.size)
            assertEquals(batch.vertexCount * 3, batch.normals.size)
            assertEquals(batch.vertexCount * 2, batch.uvs.size)
            assertTrue(batch.indices.isNotEmpty())
            for (index in batch.indices) {
                assertTrue("index $index out of ${batch.vertexCount}", index in 0 until batch.vertexCount)
            }
            assertTrue(batch.positions.all { it.isFinite() })
            assertTrue(batch.normals.all { it.isFinite() })
        }
    }

    @Test
    fun geometryIsDeterministicForTheSameScene() {
        val first = MapGeometryBuilder.build(scene())
        val second = MapGeometryBuilder.build(scene())
        assertEquals(first.batches.size, second.batches.size)
        for (i in first.batches.indices) {
            val a = first.batches[i]
            val b = second.batches[i]
            assertEquals(a.kind, b.kind)
            assertArrayEquals(a.positions, b.positions, 0f)
            assertArrayEquals(a.normals, b.normals, 0f)
            assertArrayEquals(a.uvs, b.uvs, 0f)
            assertArrayEquals(a.indices, b.indices)
        }
    }

    @Test
    fun heightAndTileInputsAreClamped() {
        val geometry = MapGeometryBuilder.build(
            scene(
                heights = listOf(listOf(0, 99, -4, 2)),
                tileM = 0f,
            ),
        )
        assertEquals(MapGeometryBuilder.MAX_LEVEL, geometry.maxLevel)
        assertEquals(2, geometry.tileCount)
        assertEquals(1f, geometry.tileM, 0.0001f)
        for (batch in geometry.batches) {
            for (y in batch.positions.indices step 3) {
                val height = batch.positions[y + 1]
                assertTrue(height <= MapGeometryBuilder.MAX_LEVEL * MapGeometryBuilder.LEVEL_M + 0.001f)
            }
        }
    }

    @Test
    fun unknownPropTypesAreIgnored() {
        val geometry = MapGeometryBuilder.build(
            scene(props = listOf(MapPropDto(type = "dragon", x = 1, y = 1))),
        )
        assertEquals(0, geometry.propCount)
        assertFalse(geometry.batches.any { it.kind == MapSurfaceKind.WOOD })
    }

    @Test
    fun oversizedMapsAreClampedInsteadOfAllocatingWithoutBound() {
        val geometry = MapGeometryBuilder.build(
            MapSceneDto(
                grid = MapGridDto(w = 500, h = 500, tileM = 1f),
                heightmap = emptyList(),
            ),
        )
        assertEquals(50, geometry.width)
        assertEquals(50, geometry.height)
        assertTrue(geometry.tileCount == 0)
    }

    @Test
    fun paletteParsesContractHexColours() {
        assertArrayEquals(floatArrayOf(1f, 0.6039216f, 0.23529412f), MapPalette.parseColor("#ff9a3c"), 0.0001f)
        assertArrayEquals(floatArrayOf(0f, 0f, 0f), MapPalette.parseColor("#000000"), 0.0001f)
        assertEquals(null, MapPalette.parseColor("ff9a3"))
        assertEquals(null, MapPalette.parseColor("#zzzzzz"))
    }
}
