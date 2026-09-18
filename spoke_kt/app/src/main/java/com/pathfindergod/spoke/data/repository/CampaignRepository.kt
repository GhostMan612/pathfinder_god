// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.repository

import com.pathfindergod.spoke.data.local.AppDatabase
import com.pathfindergod.spoke.data.local.CampaignEntity
import com.pathfindergod.spoke.data.network.HubApi
import com.pathfindergod.spoke.data.network.SummarizeRequest
import java.time.Instant
import java.util.UUID
import kotlinx.coroutines.flow.Flow
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonArray

class CampaignRepository(
    private val db: AppDatabase,
    private val api: HubApi,
) {
    fun observeActive(): Flow<CampaignEntity?> =
        db.campaignDao().observeActive()

    suspend fun createCampaign(name: String, description: String): CampaignEntity {
        val entity = CampaignEntity(
            id = UUID.randomUUID().toString(),
            name = name.ifBlank { "Untitled Campaign" },
            description = description,
            updatedAt = Instant.now().toString(),
        )
        db.campaignDao().upsert(entity)
        return entity
    }

    suspend fun summarizeRecentEvents(events: List<String>): String {
        val active = db.campaignDao().getActive()
            ?: throw IllegalStateException("No active campaign")
        val response = api.summarizeSession(SummarizeRequest(events, active.name))
        appendNote(response.summary)
        return response.summary
    }

    private suspend fun appendNote(note: String) {
        val active = db.campaignDao().getActive() ?: return
        val notes = try {
            (Json.parseToJsonElement(active.sessionNotes) as? JsonArray)
                ?.mapNotNull { (it as? JsonPrimitive)?.takeIf { p -> p.isString }?.content }
                .orEmpty()
        } catch (_: Exception) {
            emptyList()
        }
        db.campaignDao().upsert(
            active.copy(
                sessionNotes = buildJsonArray {
                    notes.forEach { add(JsonPrimitive(it)) }
                    add(JsonPrimitive(note))
                }.toString(),
                updatedAt = Instant.now().toString(),
            ),
        )
    }
}
