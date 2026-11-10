// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.map

import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.SemanticsMatcher
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import com.pathfindergod.spoke.a11y.ComposeTestActivity
import com.pathfindergod.spoke.data.network.MapFogDto
import com.pathfindergod.spoke.data.network.MapGridDto
import com.pathfindergod.spoke.data.network.MapLightDto
import com.pathfindergod.spoke.data.network.MapPropDto
import com.pathfindergod.spoke.data.network.MapSceneDto
import com.pathfindergod.spoke.data.network.MapZoneDto
import com.pathfindergod.spoke.ui.designsystem.GodTags
import com.pathfindergod.spoke.ui.theme.PathfinderGodTheme
import org.junit.Rule
import org.junit.Test

class MapDioramaSmokeTest {

    @get:Rule
    val compose = createAndroidComposeRule<ComposeTestActivity>()

    @Test
    fun filamentBuildsTheDioramaAndResetsTheCamera() {
        compose.setContent {
            PathfinderGodTheme {
                MapDiorama(
                    scene = scene(),
                    prompt = "Smoke-test crypt",
                    modifier = Modifier.fillMaxSize(),
                )
            }
        }
        compose.waitUntil(30_000) {
            compose.onAllNodes(
                SemanticsMatcher.expectValue(
                    SemanticsProperties.StateDescription,
                    "3D view ready",
                ),
            ).fetchSemanticsNodes().isNotEmpty()
        }
        compose.onNodeWithTag(GodTags.MAP_DIORAMA_RESET).assertExists().performClick()
    }

    private fun scene() = MapSceneDto(
        grid = MapGridDto(w = 6, h = 5, tileM = 1f),
        heightmap = listOf(
            listOf(0, 0, 0, 0, 0, 0),
            listOf(0, 3, 3, 3, 3, 0),
            listOf(0, 3, 1, 1, 3, 0),
            listOf(0, 3, 1, 1, 3, 0),
            listOf(0, 0, 0, 0, 0, 0),
        ),
        zones = listOf(MapZoneDto(name = "Crypt", biome = "vault", rect = listOf(2, 2, 2, 2))),
        props = listOf(
            MapPropDto(type = "pillar", x = 2, y = 2),
            MapPropDto(type = "brazier", x = 3, y = 3),
        ),
        lights = listOf(MapLightDto(x = 3, y = 2, color = "#ff9a3c", radiusM = 3f)),
        fog = MapFogDto(color = "#0a0d14", density = 0.02f),
    )
}
