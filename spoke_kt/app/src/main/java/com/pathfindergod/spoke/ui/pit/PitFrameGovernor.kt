// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.ui.pit

import android.app.Activity
import android.content.pm.ApplicationInfo
import android.os.Build
import android.util.Log
import android.view.Display
import android.view.Surface

data class PitDisplayMode(
    val modeId: Int,
    val width: Int,
    val height: Int,
    val refreshRate: Float,
)

object PitRefreshPolicy {
    const val FALLBACK_REFRESH_RATE = 60f
    const val LOWEST_REFRESH_RATE = 24f
    const val HIGHEST_REFRESH_RATE = 360f
    const val NO_MODE_ID = 0
    const val NANOS_PER_SECOND = 1_000_000_000L
    const val FRAME_RATE_API = Build.VERSION_CODES.R
    const val FRAME_RATE_STRATEGY_API = Build.VERSION_CODES.S

    fun usable(rate: Float): Boolean =
        rate.isFinite() && rate >= LOWEST_REFRESH_RATE && rate <= HIGHEST_REFRESH_RATE

    fun ratesAt(active: PitDisplayMode, modes: List<PitDisplayMode>): List<Float> = modes
        .filter { it.width == active.width && it.height == active.height }
        .map { it.refreshRate }
        .filter { usable(it) }

    fun modeIdAt(active: PitDisplayMode, modes: List<PitDisplayMode>, rate: Float): Int {
        if (!usable(rate)) return NO_MODE_ID
        return modes
            .firstOrNull {
                it.width == active.width && it.height == active.height && it.refreshRate == rate
            }
            ?.modeId
            ?: NO_MODE_ID
    }

    fun targetRate(
        active: PitDisplayMode,
        sameResolutionRates: List<Float>,
        currentRefreshRate: Float,
    ): Float = (sameResolutionRates + active.refreshRate)
        .filter { usable(it) }
        .maxOrNull()
        ?: currentRefreshRate.takeIf { usable(it) }
        ?: FALLBACK_REFRESH_RATE

    fun swapIntervalNanos(refreshRate: Float): Long {
        val rate = refreshRate.takeIf { usable(it) } ?: FALLBACK_REFRESH_RATE
        return (NANOS_PER_SECOND / rate).toLong().coerceAtLeast(1L)
    }

    fun swapIntervalSeconds(refreshRate: Float): Float =
        swapIntervalNanos(refreshRate) / NANOS_PER_SECOND.toFloat()

    fun dtCeiling(refreshRate: Float): Float =
        swapIntervalSeconds(refreshRate) * DT_CEILING_FRAMES

    fun jankThresholdNanos(refreshRate: Float): Long =
        swapIntervalNanos(refreshRate) * JANK_NUMERATOR / JANK_DENOMINATOR

    private const val DT_CEILING_FRAMES = 4f
    private const val JANK_NUMERATOR = 3L
    private const val JANK_DENOMINATOR = 2L
}

interface PitFrameClient {
    fun onHostResume(refreshRate: Float)
    fun onHostPause()
}

object PitFrameGovernor {

    var telemetryEnabled: Boolean = false
        private set

    private var host: Activity? = null
    private var resumed = false
    private var targetRate = PitRefreshPolicy.FALLBACK_REFRESH_RATE
    private var liveRate = PitRefreshPolicy.FALLBACK_REFRESH_RATE
    private var preferredModeId = PitRefreshPolicy.NO_MODE_ID
    private val clients = mutableListOf<PitFrameClient>()
    private val telemetry = PitFrameTelemetry()

    fun bind(activity: Activity) {
        host = activity
        telemetryEnabled =
            (activity.applicationInfo.flags and ApplicationInfo.FLAG_DEBUGGABLE) != 0
        readDisplay()
    }

    fun release(activity: Activity) {
        if (host !== activity) return
        pauseClients()
        clients.clear()
        host = null
        resumed = false
    }

    fun onHostResume() {
        if (host == null) return
        resumed = true
        readDisplay()
        requestFrameRate()
        clients.toList().forEach { it.onHostResume(liveRate) }
    }

    fun onHostPause() {
        resumed = false
        pauseClients()
    }

    fun attach(client: PitFrameClient) {
        if (clients.contains(client)) return
        clients.add(client)
        if (resumed) client.onHostResume(liveRate)
    }

    fun detach(client: PitFrameClient) {
        clients.remove(client)
    }

    fun refreshRateOf(display: Display?): Float =
        display?.refreshRate?.takeIf { PitRefreshPolicy.usable(it) } ?: liveRate

    fun swapIntervalSeconds(): Float = PitRefreshPolicy.swapIntervalSeconds(liveRate)

    fun dtCeiling(): Float = PitRefreshPolicy.dtCeiling(liveRate)

    fun sampleFrame(frameTimeNanos: Long) {
        if (!telemetryEnabled) return
        telemetry.sample(frameTimeNanos)
    }

    fun applyToSurface(surface: Surface) {
        if (Build.VERSION.SDK_INT < PitRefreshPolicy.FRAME_RATE_API) return
        val rate = targetRate
        runCatching {
            if (Build.VERSION.SDK_INT >= PitRefreshPolicy.FRAME_RATE_STRATEGY_API) {
                surface.setFrameRate(
                    rate,
                    Surface.FRAME_RATE_COMPATIBILITY_FIXED_SOURCE,
                    Surface.CHANGE_FRAME_RATE_ALWAYS,
                )
            } else {
                surface.setFrameRate(rate, Surface.FRAME_RATE_COMPATIBILITY_FIXED_SOURCE)
            }
        }
    }

    private fun pauseClients() {
        clients.toList().forEach { it.onHostPause() }
        if (telemetryEnabled) telemetry.publish()
    }

    @Suppress("DEPRECATION")
    private fun readDisplay() {
        val activity = host ?: return
        val display = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            activity.display
        } else {
            activity.windowManager.defaultDisplay
        } ?: return
        val mode = display.mode
        val active = PitDisplayMode(
            mode.modeId,
            mode.physicalWidth,
            mode.physicalHeight,
            mode.refreshRate,
        )
        val modes = display.supportedModes.map {
            PitDisplayMode(it.modeId, it.physicalWidth, it.physicalHeight, it.refreshRate)
        }
        val rates = PitRefreshPolicy.ratesAt(active, modes)
        targetRate = PitRefreshPolicy.targetRate(active, rates, display.refreshRate)
        preferredModeId = PitRefreshPolicy.modeIdAt(active, modes, targetRate)
        liveRate = display.refreshRate.takeIf { PitRefreshPolicy.usable(it) } ?: targetRate
        telemetry.retune(liveRate, targetRate)
    }

    private fun requestFrameRate() {
        val activity = host ?: return
        val window = activity.window
        val rate = targetRate
        val attributes = window.attributes
        attributes.preferredRefreshRate = rate
        if (preferredModeId != PitRefreshPolicy.NO_MODE_ID &&
            attributes.preferredDisplayModeId != preferredModeId
        ) {
            attributes.preferredDisplayModeId = preferredModeId
        }
        window.attributes = attributes
    }
}

internal class PitFrameTelemetry {

    private var frames = 0L
    private var janky = 0L
    private var worstNanos = 0L
    private var thresholdNanos = PitRefreshPolicy.jankThresholdNanos(
        PitRefreshPolicy.FALLBACK_REFRESH_RATE,
    )
    private var liveRate = PitRefreshPolicy.FALLBACK_REFRESH_RATE
    private var targetRate = PitRefreshPolicy.FALLBACK_REFRESH_RATE

    fun retune(live: Float, target: Float) {
        liveRate = live
        targetRate = target
        thresholdNanos = PitRefreshPolicy.jankThresholdNanos(live)
    }

    fun sample(frameTimeNanos: Long) {
        frames++
        if (frameTimeNanos > worstNanos) worstNanos = frameTimeNanos
        if (frameTimeNanos >= thresholdNanos) janky++
        if (frames >= PUBLISH_EVERY_FRAMES) publish()
    }

    fun publish() {
        if (frames == 0L) return
        Log.d(
            TAG,
            "pit frames=$frames janky=$janky jankPct=${janky * PERCENT / frames} " +
                "refreshDeciHz=${deci(liveRate)} requestDeciHz=${deci(targetRate)} " +
                "worstTenthsMs=${worstNanos / TENTHS_MS_NANOS} " +
                "thresholdTenthsMs=${thresholdNanos / TENTHS_MS_NANOS}",
        )
        frames = 0L
        janky = 0L
        worstNanos = 0L
    }

    private fun deci(rate: Float): Long = (rate * 10f).toLong()

    private companion object {
        const val TAG = "PitFrameGovernor"
        const val PERCENT = 100L
        const val PUBLISH_EVERY_FRAMES = 240L
        const val TENTHS_MS_NANOS = 100_000L
    }
}
