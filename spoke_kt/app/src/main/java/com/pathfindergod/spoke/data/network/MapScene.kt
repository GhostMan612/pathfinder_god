// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.network

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.decodeFromString
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json

@Serializable
data class MapGridDto(
    val w: Int,
    val h: Int,
    @SerialName("tile_m") val tileM: Float = 1f,
)

@Serializable
data class MapZoneDto(
    val name: String,
    val biome: String = "stone",
    val rect: List<Int> = emptyList(),
)

@Serializable
data class MapPropDto(
    val type: String,
    val x: Int,
    val y: Int,
    val rot: Int = 0,
    val scale: Float = 1f,
)

@Serializable
data class MapLightDto(
    val x: Int,
    val y: Int,
    val color: String = "#ff9a3c",
    @SerialName("radius_m") val radiusM: Float = 3f,
)

@Serializable
data class MapFogDto(
    val color: String = "#0a0d14",
    val density: Float = 0.02f,
)

@Serializable
data class MapPointDto(
    val x: Int,
    val y: Int,
)

@Serializable
data class MapDoorDto(
    val x: Int,
    val y: Int,
    val orientation: String = "ew",
    val kind: String = "wood",
)

@Serializable
data class MapCorridorDto(
    val cells: List<List<Int>> = emptyList(),
)

@Serializable
data class MapTokenDto(
    val id: String = "",
    val name: String,
    val kind: String = "monster",
    val x: Int,
    val y: Int,
    val z: Float = 0.5f,
    val color: String = "#d4af37",
)

@Serializable
data class MapSceneDto(
    val grid: MapGridDto,
    val heightmap: List<List<Int>> = emptyList(),
    val zones: List<MapZoneDto> = emptyList(),
    val props: List<MapPropDto> = emptyList(),
    val lights: List<MapLightDto> = emptyList(),
    val fog: MapFogDto? = null,
    val walkable: List<List<Int>> = emptyList(),
    val doors: List<MapDoorDto> = emptyList(),
    val corridors: List<MapCorridorDto> = emptyList(),
    val spawn: MapPointDto? = null,
    val exit: MapPointDto? = null,
    val tokens: List<MapTokenDto> = emptyList(),
    val connected: Boolean = true,
)

object MapSceneCodec {
    private val json = Json {
        ignoreUnknownKeys = true
        encodeDefaults = true
    }

    fun decode(raw: String): MapSceneDto? = runCatching {
        json.decodeFromString<MapSceneDto>(raw)
    }.getOrNull()

    fun encode(scene: MapSceneDto): String = json.encodeToString(scene)
}
