// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.pit

import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Test

class PitHostSlotTest {

    @Test
    fun unboundSlotHasNoHost() {
        assertNull(PitHostSlot<Any>().current())
    }

    @Test
    fun bindExposesTheSameInstance() {
        val slot = PitHostSlot<Any>()
        val host = Any()

        slot.bind(host)

        assertSame(host, slot.current())
    }

    @Test
    fun releaseOfAnotherHostLeavesTheBoundOneInPlace() {
        val slot = PitHostSlot<Any>()
        val bound = Any()

        slot.bind(bound)

        assertFalse(slot.release(Any()))
        assertSame(bound, slot.current())
    }

    @Test
    fun releaseOfTheBoundHostClearsIt() {
        val slot = PitHostSlot<Any>()
        val bound = Any()

        slot.bind(bound)

        assertTrue(slot.release(bound))
        assertNull(slot.current())
    }

    @Test
    fun rebindingReplacesThePreviousHost() {
        val slot = PitHostSlot<Any>()
        val first = Any()
        val second = Any()

        slot.bind(first)
        slot.bind(second)

        assertSame(second, slot.current())
        assertFalse(slot.release(first))
        assertSame(second, slot.current())
    }
}
