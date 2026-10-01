// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.pit

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class PitFramePolicyTest {

    private val garbled = PitDisplayMode(0, 720, 1604, 0f)
    private val active60 = PitDisplayMode(1, 720, 1604, 60f)
    private val modes = listOf(
        active60,
        PitDisplayMode(2, 720, 1604, 90f),
        PitDisplayMode(3, 720, 1604, 120f),
        PitDisplayMode(4, 1080, 2400, 120f),
    )

    @Test
    fun aThrottledSixtyHzPanelStillRequestsItsMaximumRefreshRate() {
        val rates = PitRefreshPolicy.ratesAt(active60, modes) + modeSupportedRates()
        assertEquals(120f, PitRefreshPolicy.targetRate(active60, rates, 60f), 1e-4f)
    }

    @Test
    fun otherResolutionsAndOutOfRangeRatesAreRejected() {
        assertEquals(listOf(60f, 90f, 120f), PitRefreshPolicy.ratesAt(active60, modes).sorted())
        assertEquals(
            PitRefreshPolicy.NO_MODE_ID,
            PitRefreshPolicy.modeIdAt(active60, modes, 480f),
        )
    }

    @Test
    fun theRequestedRateResolvesToItsModeId() {
        assertEquals(3, PitRefreshPolicy.modeIdAt(active60, modes, 120f))
        assertEquals(2, PitRefreshPolicy.modeIdAt(active60, modes, 90f))
        assertEquals(1, PitRefreshPolicy.modeIdAt(active60, modes, 60f))
    }

    @Test
    fun unusableRatesFallBackToTheLiveRefreshRateThenToSixty() {
        assertEquals(
            59.94f,
            PitRefreshPolicy.targetRate(garbled, garbageRates(), 59.94f),
            1e-4f,
        )
        assertEquals(
            PitRefreshPolicy.FALLBACK_REFRESH_RATE,
            PitRefreshPolicy.targetRate(garbled, emptyList(), 0f),
            1e-4f,
        )
    }

    @Test
    fun theSwapIntervalFollowsTheRateAndIsNeverHardcoded() {
        assertEquals(8_333_333L, PitRefreshPolicy.swapIntervalNanos(120f))
        assertEquals(11_111_111L, PitRefreshPolicy.swapIntervalNanos(90f))
        assertEquals(16_666_667L, PitRefreshPolicy.swapIntervalNanos(60f))
        assertEquals(
            PitRefreshPolicy.swapIntervalNanos(PitRefreshPolicy.FALLBACK_REFRESH_RATE),
            PitRefreshPolicy.swapIntervalNanos(0f),
        )
    }

    @Test
    fun aFrameIsJankyOnlyOnceItOverrunsTheSwapInterval() {
        val interval = PitRefreshPolicy.swapIntervalNanos(120f)
        val threshold = PitRefreshPolicy.jankThresholdNanos(120f)
        assertTrue("threshold clears one interval", threshold > interval)
        assertTrue("threshold still clears two", threshold < interval * 2L)
    }

    @Test
    fun theIntegrationStepIsCappedByTheLiveFrameInterval() {
        assertEquals(4f / 120f, PitRefreshPolicy.dtCeiling(120f), 1e-5f)
        assertEquals(4f / 60f, PitRefreshPolicy.dtCeiling(60f), 1e-4f)
        assertTrue(
            "a faster panel tightens the cap",
            PitRefreshPolicy.dtCeiling(120f) < PitRefreshPolicy.dtCeiling(60f),
        )
    }

    private fun modeSupportedRates(): List<Float> = listOf(120f, 90f, 60f)

    private fun garbageRates(): List<Float> =
        listOf(0f, -1f, Float.NaN, Float.POSITIVE_INFINITY, 4_800f)
}
