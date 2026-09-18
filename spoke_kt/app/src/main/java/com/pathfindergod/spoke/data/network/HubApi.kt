// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.network

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement
import retrofit2.http.Body
import retrofit2.http.POST

@Serializable
data class StrikeRequest(
    @SerialName("attack_roll") val attackRoll: Int,
    @SerialName("target_ac") val targetAc: Int,
    @SerialName("damage_roll") val damageRoll: Int,
    @SerialName("target_hp") val targetHp: Int,
    @SerialName("target_temp_hp") val targetTempHp: Int = 0,
)

@Serializable
data class StrikeResponse(
    val outcome: String,
    @SerialName("damage_dealt") val damageDealt: Int,
    @SerialName("new_hp") val newHp: Int,
    @SerialName("new_temp_hp") val newTempHp: Int,
    val notes: String,
)

@Serializable
data class ConditionItem(
    val name: String,
    val value: Int = 1,
    @SerialName("duration_rounds") val durationRounds: Int? = null,
)

@Serializable
data class EndTurnRequest(
    val conditions: List<ConditionItem> = emptyList(),
    @SerialName("current_hp") val currentHp: Int = 0,
)

@Serializable
data class EndTurnResponse(
    val conditions: List<ConditionItem> = emptyList(),
    val notes: String = "",
    @SerialName("damage_taken") val damageTaken: Int = 0,
)

@Serializable
data class GenerateRequest(
    val prompt: String,
    val edition: String = "both",
)

@Serializable
data class GenerateResponse(
    val answer: String,
    val backend: String,
    val mode: String,
    val edition: String,
    val sources: List<Map<String, JsonElement>> = emptyList(),
)

@Serializable
data class MapGenerateResponse(
    val valid: Boolean = false,
    @SerialName("gm_base64_png") val gmBase64Png: String = "",
    @SerialName("player_base64_png") val playerBase64Png: String = "",
    val width: Int = 0,
    val height: Int = 0,
)

@Serializable
data class SummarizeRequest(
    val events: List<String>,
    @SerialName("campaign_name") val campaignName: String,
)

@Serializable
data class SummarizeResponse(
    val summary: String = "",
    @SerialName("event_count") val eventCount: Int = 0,
)

@Serializable
data class LootResponse(
    val valid: Boolean,
    val item: Map<String, JsonElement>? = null,
    @SerialName("craft_dc") val craftDc: Int? = null,
    val errors: List<String> = emptyList(),
)

interface HubApi {
    @POST("combat/resolve-strike")
    suspend fun resolveStrike(@Body request: StrikeRequest): StrikeResponse

    @POST("combat/end-turn")
    suspend fun endTurn(@Body request: EndTurnRequest): EndTurnResponse

    @POST("generate/loot")
    suspend fun generateLoot(@Body request: GenerateRequest): LootResponse

    @POST("generate/map")
    suspend fun generateMap(@Body request: GenerateRequest): MapGenerateResponse

    @POST("generate/character")
    suspend fun generateCharacter(@Body request: GenerateRequest): GenerateResponse

    @POST("campaign/summarize-session")
    suspend fun summarizeSession(@Body request: SummarizeRequest): SummarizeResponse
}
