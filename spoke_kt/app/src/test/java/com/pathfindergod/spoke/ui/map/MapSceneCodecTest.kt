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

    @Test
    fun decodesPlayableTokensDoorsCorridorsSpawnAndExit() {
        val playable = """
            {
              "grid": {"w": 6, "h": 5, "tile_m": 1.0},
              "heightmap": [[0,0,0,0,0,0],[0,3,3,3,3,0],[0,3,1,1,1,0],[0,3,1,1,3,0],[0,3,3,3,3,0]],
              "walkable": [[0,0,0,0,0,0],[0,0,0,0,0,0],[0,0,1,1,1,0],[0,0,1,1,0,0],[0,0,0,0,0,0]],
              "doors": [{"x": 4, "y": 2, "orientation": "ew", "kind": "wood"}],
              "corridors": [{"cells": [[4, 2], [5, 2]]}],
              "spawn": {"x": 2, "y": 2},
              "exit": {"x": 3, "y": 3},
              "tokens": [
                {"id": "hero-1", "name": "SAMPLE HERO", "kind": "hero", "x": 2, "y": 2, "z": 0.5, "color": "#3b82f6"},
                {"id": "monster-1", "name": "SAMPLE GOBLIN", "kind": "monster", "x": 3, "y": 2, "z": 0.5, "color": "#dc2626"},
                {"id": "npc-1", "name": "SAMPLE ELDER", "kind": "npc", "x": 2, "y": 3, "z": 0.5, "color": "#22c55e"},
                {"id": "loot-1", "name": "Sunblade", "kind": "loot", "x": 3, "y": 3, "z": 0.5, "color": "#eab308"}
              ],
              "connected": true
            }
        """.trimIndent()
        val scene = MapSceneCodec.decode(playable)
        assertNotNull(scene)
        scene!!
        assertTrue(scene.connected)
        assertEquals(2, scene.spawn!!.x)
        assertEquals(3, scene.exit!!.y)
        assertEquals(1, scene.doors.size)
        assertEquals("ew", scene.doors.single().orientation)
        assertEquals(1, scene.corridors.size)
        assertEquals(4, scene.tokens.size)
        assertEquals(listOf("hero", "monster", "npc", "loot"), scene.tokens.map { it.kind })
        assertEquals(scene, MapSceneCodec.decode(MapSceneCodec.encode(scene)))
    }
}
