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
data class MapSceneDto(
    val grid: MapGridDto,
    val heightmap: List<List<Int>> = emptyList(),
    val zones: List<MapZoneDto> = emptyList(),
    val props: List<MapPropDto> = emptyList(),
    val lights: List<MapLightDto> = emptyList(),
    val fog: MapFogDto? = null,
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
