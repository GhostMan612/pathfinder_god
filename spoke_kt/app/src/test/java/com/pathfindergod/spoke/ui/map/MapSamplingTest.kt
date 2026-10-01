// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.map

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class MapSamplingTest {

    @Test
    fun smallImagesAreNotDownsampled() {
        assertEquals(1, mapSampleSize(512, 512, 512))
        assertEquals(1, mapSampleSize(400, 900, 512))
    }

    @Test
    fun largeImagesAreDownsampledByPowersOfTwo() {
        assertEquals(2, mapSampleSize(1024, 1024, 512))
        assertEquals(4, mapSampleSize(2048, 2048, 512))
        assertEquals(8, mapSampleSize(4096, 2048, 512))
    }

    @Test
    fun theLongerEdgeDrivesTheSample() {
        assertEquals(2, mapSampleSize(100, 1024, 512))
        assertEquals(2, mapSampleSize(1024, 100, 512))
        assertEquals(1, mapSampleSize(300, 200, 512))
    }

    @Test
    fun samplingStopsAtTheRequestedSize() {
        val sample = mapSampleSize(4000, 3000, 512)
        assertTrue(sample > 1)
        assertTrue(4000 / sample <= 2048)
    }

    @Test
    fun degenerateInputsFallBackToOne() {
        assertEquals(1, mapSampleSize(0, 0, 512))
        assertEquals(1, mapSampleSize(-1, 100, 512))
        assertEquals(1, mapSampleSize(4000, 3000, 0))
    }

    @Test
    fun offsetsClampToTheScaledViewport() {
        val clamped = mapBoundsClamp(900f, -900f, 1000f, 800f, 2f)
        assertEquals(500f, clamped[0], 0.01f)
        assertEquals(-400f, clamped[1], 0.01f)
    }

    @Test
    fun offsetsAreFreeWhileZoomedOut() {
        val clamped = mapBoundsClamp(50f, -50f, 1000f, 800f, 1f)
        assertEquals(0f, clamped[0], 0.01f)
        assertEquals(0f, clamped[1], 0.01f)
    }

    @Test
    fun offsetsNeverInvertWhilePanning() {
        val clamped = mapBoundsClamp(-4000f, 4000f, 1000f, 800f, 3f)
        assertEquals(-1000f, clamped[0], 0.01f)
        assertEquals(800f, clamped[1], 0.01f)
    }
}
