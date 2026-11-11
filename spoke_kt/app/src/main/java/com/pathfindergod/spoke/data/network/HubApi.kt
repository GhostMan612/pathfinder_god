// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.network

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path

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
    @SerialName("campaign_id") val campaignId: Int? = null,
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
    val scene: MapSceneDto? = null,
    val error: String? = null,
    @SerialName("encounter_id") val encounterId: Int? = null,
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

@Serializable
data class CombatSceneRequest(
    @SerialName("campaign_id") val campaignId: Int = 1,
    val scene: String,
)

@Serializable
data class CombatSceneResponse(
    @SerialName("campaign_id") val campaignId: Int,
    val scene: String,
)

@Serializable
data class AskRequest(
    val query: String,
    val edition: String = "both",
    val mode: String? = null,
    val history: List<List<String>> = emptyList(),
    @SerialName("campaign_id") val campaignId: Int = 1,
)

@Serializable
data class AskResponse(
    val answer: String,
    val backend: String = "ollama",
    val mode: String = "",
    val edition: String = "both",
    val sources: List<Map<String, JsonElement>> = emptyList(),
)

@Serializable
data class CreateCampaignRequest(
    val name: String,
    val edition: String = "2e",
    val premise: String = "",
    @SerialName("hero_prompt") val heroPrompt: String? = null,
)

@Serializable
data class CreateCampaignResponse(
    @SerialName("campaign_id") val campaignId: Int,
    val name: String,
    val edition: String,
    val location: String? = null,
    val quest: String? = null,
    val hero: String? = null,
    @SerialName("opening_narration") val openingNarration: String,
    val source: String = "fallback",
)

@Serializable
data class TurnRequest(
    val action: String,
    val actor: String = "player",
    val seed: Int? = null,
)

@Serializable
data class TurnResponse(
    @SerialName("campaign_id") val campaignId: Int,
    @SerialName("turn_num") val turnNum: Int,
    val narration: String,
    @SerialName("dice_rolls") val diceRolls: List<Map<String, JsonElement>> = emptyList(),
    @SerialName("hp_changes") val hpChanges: List<Map<String, JsonElement>> = emptyList(),
    val conditions: List<Map<String, JsonElement>> = emptyList(),
    @SerialName("quest_updates") val questUpdates: List<Map<String, JsonElement>> = emptyList(),
    val location: String? = null,
    val phase: String = "exploration",
    val round: Int = 0,
    @SerialName("active_combatant") val activeCombatant: String? = null,
    val choices: List<String> = emptyList(),
    val seed: Int = 0,
    val source: String = "fallback",
    val kind: String = "other",
)

@Serializable
data class SoloStateResponse(
    @SerialName("campaign_id") val campaignId: Int,
    val name: String,
    val edition: String,
    val phase: String,
    val round: Int,
    val location: String? = null,
    @SerialName("location_id") val locationId: Int? = null,
    @SerialName("active_combatant_id") val activeCombatantId: Int? = null,
    val combatants: List<Map<String, JsonElement>> = emptyList(),
    val quests: List<Map<String, JsonElement>> = emptyList(),
    @SerialName("recent_turns") val recentTurns: List<Map<String, JsonElement>> = emptyList(),
    val chronicle: String = "",
)

interface HubApi {
    @POST("ask")
    suspend fun ask(@Body request: AskRequest): AskResponse

    @POST("campaign/create")
    suspend fun createSoloCampaign(@Body request: CreateCampaignRequest): CreateCampaignResponse

    @POST("campaign/{campaign_id}/turn")
    suspend fun takeSoloTurn(
        @Path("campaign_id") campaignId: Int,
        @Body request: TurnRequest,
    ): TurnResponse

    @GET("campaign/{campaign_id}/state")
    suspend fun getSoloState(@Path("campaign_id") campaignId: Int): SoloStateResponse

    @POST("combat/resolve-strike")
    suspend fun resolveStrike(@Body request: StrikeRequest): StrikeResponse

    // BP-08: the Spoke combat tracker is the PRODUCER for this endpoint. Until
    // now only the Hub-side write existed, so the GM's combat context always
    // described the last session rather than the live table.
    @POST("combat/scene")
    suspend fun setCombatScene(@Body request: CombatSceneRequest): CombatSceneResponse

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
