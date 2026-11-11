// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.viewmodel

import com.pathfindergod.spoke.data.network.AskRequest
import com.pathfindergod.spoke.data.network.AskResponse
import com.pathfindergod.spoke.data.network.BuildCharacterRequest
import com.pathfindergod.spoke.data.network.BuildCharacterResponse
import com.pathfindergod.spoke.data.network.CombatSceneRequest
import com.pathfindergod.spoke.data.network.CombatSceneResponse
import com.pathfindergod.spoke.data.network.CreateCampaignRequest
import com.pathfindergod.spoke.data.network.CreateCampaignResponse
import com.pathfindergod.spoke.data.network.EncounterRequest
import com.pathfindergod.spoke.data.network.EncounterResponse
import com.pathfindergod.spoke.data.network.EndTurnRequest
import com.pathfindergod.spoke.data.network.EndTurnResponse
import com.pathfindergod.spoke.data.network.GenerateRequest
import com.pathfindergod.spoke.data.network.GmStreamSource
import com.pathfindergod.spoke.data.network.HubApi
import com.pathfindergod.spoke.data.network.LootResponse
import com.pathfindergod.spoke.data.network.MapGenerateResponse
import com.pathfindergod.spoke.data.network.MapRequest
import com.pathfindergod.spoke.data.network.SoloStateResponse
import com.pathfindergod.spoke.data.network.StreamEvent
import com.pathfindergod.spoke.data.network.StrikeRequest
import com.pathfindergod.spoke.data.network.StrikeResponse
import com.pathfindergod.spoke.data.network.SummarizeRequest
import com.pathfindergod.spoke.data.network.SummarizeResponse
import com.pathfindergod.spoke.data.network.TurnRequest
import com.pathfindergod.spoke.data.network.TurnResponse
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOf
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class GmChatViewModelTest {

    private open class FakeHubApi : HubApi {
        var lastAskRequest: AskRequest? = null
        var lastTurnRequest: TurnRequest? = null

        override suspend fun ask(request: AskRequest): AskResponse {
            lastAskRequest = request
            return AskResponse(
                answer = "Flanking makes the foe off-guard.",
                backend = "ollama",
                mode = "campaign",
                edition = request.edition,
                sources = listOf(
                    mapOf(
                        "source_book" to JsonPrimitive("Player Core"),
                        "name" to JsonPrimitive("Flanking"),
                    ),
                ),
            )
        }

        override suspend fun createSoloCampaign(request: CreateCampaignRequest): CreateCampaignResponse =
            CreateCampaignResponse(
                campaignId = 1,
                name = request.name,
                edition = request.edition,
                openingNarration = "Welcome to SAMPLE CRYPT.",
            )

        override suspend fun takeSoloTurn(campaignId: Int, request: TurnRequest): TurnResponse {
            lastTurnRequest = request
            return TurnResponse(
                campaignId = campaignId,
                turnNum = 2,
                narration = "REST fallback resolved the turn.",
                diceRolls = listOf(
                    mapOf(
                        "notation" to JsonPrimitive("d20"),
                        "rolls" to JsonArray(listOf(JsonPrimitive(15))),
                        "total" to JsonPrimitive(18),
                    ),
                ),
                hpChanges = listOf(
                    mapOf(
                        "name" to JsonPrimitive("SAMPLE GOBLIN"),
                        "hp" to JsonPrimitive(4),
                        "max_hp" to JsonPrimitive(12),
                        "damage" to JsonPrimitive(8),
                    ),
                ),
                conditions = emptyList(),
                location = "SAMPLE CRYPT",
                phase = "combat",
                round = 2,
                activeCombatant = "SAMPLE HERO",
                choices = listOf("Press the attack", "Step back"),
                seed = request.seed ?: 99,
                source = "fallback",
                kind = "attack",
            )
        }

        override suspend fun getSoloState(campaignId: Int): SoloStateResponse =
            SoloStateResponse(
                campaignId = campaignId,
                name = "SAMPLE CAMPAIGN",
                edition = "2e",
                phase = "combat",
                round = 3,
                location = "SAMPLE CRYPT",
                activeCombatantId = 10,
                combatants = listOf(
                    mapOf(
                        "id" to JsonPrimitive(10),
                        "name" to JsonPrimitive("SAMPLE HERO"),
                        "conditions" to JsonArray(
                            listOf(
                                JsonObject(
                                    mapOf(
                                        "name" to JsonPrimitive("frightened"),
                                        "value" to JsonPrimitive(1),
                                    ),
                                ),
                            ),
                        ),
                    ),
                ),
            )

        override suspend fun resolveStrike(request: StrikeRequest): StrikeResponse =
            throw UnsupportedOperationException()

        override suspend fun setCombatScene(request: CombatSceneRequest): CombatSceneResponse =
            throw UnsupportedOperationException()

        override suspend fun endTurn(request: EndTurnRequest): EndTurnResponse =
            throw UnsupportedOperationException()

        override suspend fun generateLoot(request: GenerateRequest): LootResponse =
            throw UnsupportedOperationException()

        override suspend fun generateMap(request: MapRequest): MapGenerateResponse =
            throw UnsupportedOperationException()

        override suspend fun generateCharacter(request: BuildCharacterRequest): BuildCharacterResponse =
            throw UnsupportedOperationException()

        override suspend fun summarizeSession(request: SummarizeRequest): SummarizeResponse =
            throw UnsupportedOperationException()

        override suspend fun generateEncounter(request: EncounterRequest): EncounterResponse =
            throw UnsupportedOperationException()
    }

    @Test
    fun `ask populates answer backend and sources from POST ask`() {
        val api = FakeHubApi()
        val stream = GmStreamSource { _, _, _, _, _ -> flowOf() }
        val vm = GmChatViewModel(
            api = api,
            streamClient = stream,
            streamUrlProvider = { "ws://127.0.0.1:8000/stream" },
            dispatcher = Dispatchers.Unconfined,
        )

        vm.ask("How does flanking work?", edition = "2e")

        val state = vm.state.value
        assertFalse(state.isBusy)
        assertNull(state.error)
        assertEquals(1, state.entries.size)
        val entry = state.entries.single()
        assertTrue(entry.isAsk)
        assertEquals("How does flanking work?", entry.prompt)
        assertEquals("Flanking makes the foe off-guard.", entry.narration)
        assertEquals("ollama", entry.backend)
        assertEquals(listOf("Player Core - Flanking"), entry.sources)
    }

    @Test
    fun `takeTurn streams dice hp conditions narration and final state over websocket`() {
        val api = FakeHubApi()
        val finalResult = TurnResponse(
            campaignId = 1,
            turnNum = 1,
            narration = "You strike SAMPLE GOBLIN. It reels backward.",
            diceRolls = listOf(
                mapOf(
                    "notation" to JsonPrimitive("d20"),
                    "rolls" to JsonArray(listOf(JsonPrimitive(17))),
                    "total" to JsonPrimitive(21),
                ),
            ),
            hpChanges = listOf(
                mapOf(
                    "name" to JsonPrimitive("SAMPLE GOBLIN"),
                    "hp" to JsonPrimitive(6),
                    "max_hp" to JsonPrimitive(12),
                    "damage" to JsonPrimitive(6),
                ),
            ),
            conditions = listOf(
                mapOf(
                    "combatant" to JsonPrimitive("SAMPLE GOBLIN"),
                    "name" to JsonPrimitive("off-guard"),
                    "value" to JsonPrimitive(1),
                ),
            ),
            location = "SAMPLE HALL",
            phase = "combat",
            round = 1,
            activeCombatant = "SAMPLE HERO",
            choices = listOf("Strike again", "Raise shield", "Step away"),
            seed = 42,
            source = "llm",
            kind = "attack",
        )
        val stream = GmStreamSource { _, campaignId, _, _, _ ->
            flowOf(
                StreamEvent(
                    type = "start",
                    campaignId = campaignId,
                    turnNum = 1,
                    phase = "combat",
                    round = 1,
                ),
                StreamEvent(
                    type = "dice",
                    diceRolls = finalResult.diceRolls,
                ),
                StreamEvent(
                    type = "hp",
                    hpChanges = finalResult.hpChanges,
                ),
                StreamEvent(
                    type = "conditions",
                    conditions = finalResult.conditions,
                ),
                StreamEvent(
                    type = "narration",
                    text = "You strike SAMPLE GOBLIN. ",
                ),
                StreamEvent(
                    type = "narration",
                    text = "It reels backward.",
                ),
                StreamEvent(
                    type = "end",
                    result = finalResult,
                ),
            )
        }
        val vm = GmChatViewModel(
            api = api,
            streamClient = stream,
            streamUrlProvider = { "ws://127.0.0.1:8000/stream" },
            dispatcher = Dispatchers.Unconfined,
        )

        vm.takeTurn("I strike SAMPLE GOBLIN", seed = 42)

        val state = vm.state.value
        assertFalse(state.isBusy)
        assertNull(state.error)
        assertNull(api.lastTurnRequest)
        assertEquals("combat", state.campaignState.phase)
        assertEquals(1, state.campaignState.round)
        assertEquals("SAMPLE HALL", state.campaignState.location)
        assertEquals("SAMPLE HERO", state.campaignState.activeCombatant)
        assertEquals(listOf("Strike again", "Raise shield", "Step away"), state.activeChoices)

        val entry = state.entries.single()
        assertEquals(1, entry.turnNum)
        assertEquals("You strike SAMPLE GOBLIN. It reels backward.", entry.narration)
        assertEquals(21, entry.diceRolls.single().total)
        assertEquals("SAMPLE GOBLIN", entry.hpChanges.single().name)
        assertEquals(6, entry.hpChanges.single().deltaAmount)
        assertFalse(entry.hpChanges.single().isHeal)
        assertEquals("off-guard", entry.conditions.single().name)
    }

    @Test
    fun `takeTurn falls back to REST takeSoloTurn when websocket fails`() {
        val api = FakeHubApi()
        val failingStream = GmStreamSource { _, _, _, _, _ ->
            flow<StreamEvent> {
                throw IllegalStateException("socket closed")
            }
        }
        val vm = GmChatViewModel(
            api = api,
            streamClient = failingStream,
            streamUrlProvider = { "ws://127.0.0.1:8000/stream" },
            dispatcher = Dispatchers.Unconfined,
        )

        vm.takeTurn("I attack SAMPLE GOBLIN", seed = 99)

        val state = vm.state.value
        assertFalse(state.isBusy)
        assertNull(state.error)
        assertEquals("I attack SAMPLE GOBLIN", api.lastTurnRequest?.action)
        val entry = state.entries.single()
        assertEquals(2, entry.turnNum)
        assertEquals("REST fallback resolved the turn.", entry.narration)
        assertEquals(18, entry.diceRolls.single().total)
        assertEquals(8, entry.hpChanges.single().deltaAmount)
        assertEquals(listOf("Press the attack", "Step back"), state.activeChoices)
    }

    @Test
    fun `refreshCampaignState updates phase round location and conditions`() {
        val api = FakeHubApi()
        val stream = GmStreamSource { _, _, _, _, _ -> flowOf() }
        val vm = GmChatViewModel(
            api = api,
            streamClient = stream,
            streamUrlProvider = { "ws://127.0.0.1:8000/stream" },
            dispatcher = Dispatchers.Unconfined,
        )

        vm.refreshCampaignState(1)

        val campaign = vm.state.value.campaignState
        assertEquals("SAMPLE CAMPAIGN", campaign.name)
        assertEquals("combat", campaign.phase)
        assertEquals(3, campaign.round)
        assertEquals("SAMPLE CRYPT", campaign.location)
        assertEquals("SAMPLE HERO", campaign.activeCombatant)
        assertEquals("frightened", campaign.conditions.single().name)
        assertEquals(1, campaign.conditions.single().value)
    }
}
