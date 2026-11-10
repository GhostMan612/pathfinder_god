// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.pit

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class PitMaterialSmokeTest {

    @Test
    fun allPitMaterialsCompileForTheDevice() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val prepared = PitMaterial.prepare(context, PitMaterial.Kind.values().toList())
        assertEquals(3, prepared.size)
        for ((kind, bytes) in prepared) {
            assertTrue("$kind produced an empty material", bytes.isNotEmpty())
        }
    }
}
