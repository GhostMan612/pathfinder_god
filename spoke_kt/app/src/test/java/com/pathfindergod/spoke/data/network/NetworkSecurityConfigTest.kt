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

    @Test
    fun releaseCleartextExceptionMatchesOnlyEmulatorHost() {
        val file = File("src/main/res/xml/network_security_config.xml")
        val doc = DocumentBuilderFactory.newInstance().newDocumentBuilder().parse(file)
        val domains = doc.getElementsByTagName("domain")
        assertEquals(1, domains.length)
        val only = domains.item(0) as Element
        assertEquals("10.0.2.2", only.textContent.trim())
        assertEquals("false", only.getAttribute("includeSubdomains"))
        val domainConfigs = doc.getElementsByTagName("domain-config")
        assertEquals(1, domainConfigs.length)
        assertEquals(
            "true",
            (domainConfigs.item(0) as Element).getAttribute("cleartextTrafficPermitted"),
        )
    }

}
