// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.map

import com.pathfindergod.spoke.data.network.MapSceneCodec
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class MapSceneCodecTest {

    private val payload = """
        {
          "grid": {"w": 4, "h": 3, "tile_m": 1.0},
          "heightmap": [[0, 0, 0, 0], [0, 1, 3, 0], [0, 1, 1, 0]],
          "zones": [{"name": "Tavern", "biome": "tavern", "rect": [1, 1, 2, 1]}],
          "props": [
            {"type": "crate", "x": 1, "y": 1, "rot": 90, "scale": 1.0},
            {"type": "brazier", "x": 2, "y": 1, "rot": 0, "scale": 1.0}
          ],
          "lights": [{"x": 2, "y": 1, "color": "#ff9a3c", "radius_m": 3.0}],
          "fog": {"color": "#0a0d14", "density": 0.02}
        }
    """.trimIndent()

    @Test
    fun decodesTheHubSceneContract() {
        val scene = MapSceneCodec.decode(payload)
        assertNotNull(scene)
        scene!!
        assertEquals(4, scene.grid.w)
        assertEquals(3, scene.grid.h)
        assertEquals(1f, scene.grid.tileM, 0.0001f)
        assertEquals(3, scene.heightmap.size)
        assertEquals(listOf(0, 1, 3, 0), scene.heightmap[1])
        assertEquals("tavern", scene.zones.single().biome)
        assertEquals(listOf(1, 1, 2, 1), scene.zones.single().rect)
        assertEquals(2, scene.props.size)
        assertEquals(90, scene.props.first().rot)
        assertEquals(3f, scene.lights.single().radiusM, 0.0001f)
        assertEquals(0.02f, scene.fog!!.density, 0.0001f)
    }

    @Test
    fun missingOptionalCollectionsBecomeEmpty() {
        val scene = MapSceneCodec.decode("""{"grid":{"w":2,"h":2,"tile_m":1.0}}""")
        assertNotNull(scene)
        scene!!
        assertTrue(scene.heightmap.isEmpty())
        assertTrue(scene.zones.isEmpty())
        assertTrue(scene.props.isEmpty())
        assertTrue(scene.lights.isEmpty())
        assertNull(scene.fog)
    }

    @Test
    fun unknownFieldsAreIgnored() {
        val scene = MapSceneCodec.decode(
            """{"grid":{"w":2,"h":2,"tile_m":1.0},"future_field":{"nested":true}}""",
        )
        assertNotNull(scene)
    }

    @Test
    fun malformedJsonReturnsNullInsteadOfCrashingTheViewer() {
        assertNull(MapSceneCodec.decode("not json"))
        assertNull(MapSceneCodec.decode("""{"heightmap":[]}"""))
    }

    @Test
    fun encodeRoundTripsTheScene() {
        val scene = MapSceneCodec.decode(payload)!!
        val encoded = MapSceneCodec.encode(scene)
        val decoded = MapSceneCodec.decode(encoded)
        assertEquals(scene, decoded)
    }
}
