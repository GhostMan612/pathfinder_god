// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.a11y

import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.unit.LayoutDirection
import androidx.test.platform.app.InstrumentationRegistry
import com.pathfindergod.spoke.R
import com.pathfindergod.spoke.ui.designsystem.godRtlText
import com.pathfindergod.spoke.ui.theme.PathfinderGodTheme
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Rule
import org.junit.Test

class RtlGlyphTest {
    @get:Rule
    val compose = createAndroidComposeRule<ComposeTestActivity>()

    @Test
    fun backLinkGlyph_isLeftPointingInLtr() {
        val (ltr, rtl) = resolvePair(R.string.character_back, R.string.character_back_rtl)
        assertEquals(string(R.string.character_back), ltr)
        assertNotEquals(ltr, rtl)
    }

    @Test
    fun backLinkGlyph_isRightPointingInRtl() {
        val (_, rtl) = resolvePair(R.string.character_back, R.string.character_back_rtl)
        assertEquals(string(R.string.character_back_rtl), rtl)
    }

    @Test
    fun mapBackLinkGlyph_isMirroredInRtl() {
        val (ltr, rtl) = resolvePair(R.string.map_back, R.string.map_back_rtl)
        assertEquals(string(R.string.map_back), ltr)
        assertNotEquals(ltr, rtl)
        assertEquals(string(R.string.map_back_rtl), rtl)
    }

    @Test
    fun missingHeroBackLinkGlyph_isMirroredInRtl() {
        val (ltr, rtl) = resolvePair(
            R.string.hero_missing_back,
            R.string.hero_missing_back_rtl,
        )
        assertEquals(string(R.string.hero_missing_back), ltr)
        assertNotEquals(ltr, rtl)
        assertEquals(string(R.string.hero_missing_back_rtl), rtl)
    }

    @Test
    fun collapsedDisclosureGlyph_isMirroredInRtl() {
        val (ltr, rtl) = resolvePair(
            R.string.disclosure_collapsed,
            R.string.disclosure_collapsed_rtl,
        )
        assertEquals(string(R.string.disclosure_collapsed), ltr)
        assertNotEquals(ltr, rtl)
        assertEquals(string(R.string.disclosure_collapsed_rtl), rtl)
    }

    @Test
    fun everyRtlPairedStringDeclaresBothHalves() {
        assertNotEquals("", string(R.string.character_back_rtl))
        assertNotEquals("", string(R.string.map_back_rtl))
        assertNotEquals("", string(R.string.hero_missing_back_rtl))
        assertNotEquals("", string(R.string.disclosure_collapsed_rtl))
    }

    @Test
    fun everyRtlPairHasDistinctHalves() {
        assertNotEquals(
            string(R.string.character_back),
            string(R.string.character_back_rtl),
        )
        assertNotEquals(string(R.string.map_back), string(R.string.map_back_rtl))
        assertNotEquals(
            string(R.string.hero_missing_back),
            string(R.string.hero_missing_back_rtl),
        )
        assertNotEquals(
            string(R.string.disclosure_collapsed),
            string(R.string.disclosure_collapsed_rtl),
        )
    }

    @Test
    fun expandedDisclosureGlyphIsASingleDirectionNeutralResource() {
        assertNotEquals("", string(R.string.disclosure_expanded))
        assertNotEquals(
            string(R.string.disclosure_expanded),
            string(R.string.disclosure_collapsed_rtl),
        )
    }

    private fun string(res: Int): String =
        InstrumentationRegistry.getInstrumentation().targetContext.getString(res)

    private fun resolvePair(ltrRes: Int, rtlRes: Int): Pair<String, String> {
        var ltr = ""
        var rtl = ""
        compose.setContent {
            PathfinderGodTheme {
                CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Ltr) {
                    ltr = godRtlText(ltrRes, rtlRes)
                }
                CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Rtl) {
                    rtl = godRtlText(ltrRes, rtlRes)
                }
            }
        }
        compose.waitForIdle()
        return ltr to rtl
    }
}
