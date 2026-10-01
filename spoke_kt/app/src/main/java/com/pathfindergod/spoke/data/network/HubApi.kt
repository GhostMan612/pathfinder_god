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
data class MapRequest(
    val prompt: String,
    @SerialName("grid_enabled") val gridEnabled: Boolean = true,
)

@Serializable
data class MapGenerateResponse(
    val valid: Boolean = false,
    // The contract types these anyOf[integer|string, null], so they must be
    // nullable. Non-null defaults would throw on the legal value null.
    @SerialName("gm_base64_png") val gmBase64Png: String? = null,
    @SerialName("player_base64_png") val playerBase64Png: String? = null,
    val width: Int? = null,
    val height: Int? = null,
    val error: String? = null,
)

@Serializable
data class BuildCharacterRequest(val prompt: String)

@Serializable
data class BuildCharacterResponse(
    val valid: Boolean,
    val character: Map<String, JsonElement>? = null,
    val errors: List<String> = emptyList(),
)

@Serializable
data class EncounterRequest(
    @SerialName("party_level") val partyLevel: Int,
    @SerialName("party_size") val partySize: Int,
    val threat: String,
    val theme: String,
)

@Serializable
data class EncounterMonster(
    val name: String = "",
    val count: Int = 1,
    val level: Int = 0,
    @SerialName("xp_each") val xpEach: Int = 0,
    @SerialName("total_xp") val totalXp: Int = 0,
    @SerialName("source_book") val sourceBook: String = "",
)

@Serializable
data class EncounterResponse(
    @SerialName("target_xp") val targetXp: Int = 0,
    @SerialName("total_xp") val totalXp: Int = 0,
    val threat: String = "",
    val theme: String = "",
    val monsters: List<EncounterMonster> = emptyList(),
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

    // There is no POST /generate/map. That path silently matched
    // /generate/{kind} with kind="map", which returns 200 with a prose answer
    // instead of a map - so the Map tab reported "empty" forever. The contract
    // route is /map/generate and it takes MapRequest, not GenerateRequest.
    @POST("map/generate")
    suspend fun generateMap(@Body request: MapRequest): MapGenerateResponse

    // /generate/character returns BuildCharacterResponse, not GenerateResponse.
    // Decoding {valid, character, errors} as GenerateResponse threw
    // MissingFieldException on the required `answer` field.
    @POST("generate/character")
    suspend fun generateCharacter(@Body request: BuildCharacterRequest): BuildCharacterResponse

    @POST("campaign/summarize-session")
    suspend fun summarizeSession(@Body request: SummarizeRequest): SummarizeResponse

    @POST("encounter/generate")
    suspend fun generateEncounter(@Body request: EncounterRequest): EncounterResponse
}
