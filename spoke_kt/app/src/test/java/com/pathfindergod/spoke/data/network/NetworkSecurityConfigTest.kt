// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.data.network

import java.io.File
import javax.xml.parsers.DocumentBuilderFactory
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.w3c.dom.Element

class NetworkSecurityConfigTest {

    private fun baseConfig(sourceSet: String): Element {
        val file = File("src/$sourceSet/res/xml/network_security_config.xml")
        assertTrue("missing ${file.path}", file.isFile)
        val doc = DocumentBuilderFactory.newInstance().newDocumentBuilder().parse(file)
        return doc.getElementsByTagName("base-config").item(0) as Element
    }

    @Test
    fun debugBuildPermitsCleartextToAnyLanHub() {
        assertEquals("true", baseConfig("debug").getAttribute("cleartextTrafficPermitted"))
    }

    @Test
    fun mainBuildKeepsCleartextLockedByDefault() {
        assertEquals("false", baseConfig("main").getAttribute("cleartextTrafficPermitted"))
    }
}
