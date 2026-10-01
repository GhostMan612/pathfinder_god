// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.service

import android.content.Context
import android.content.res.AssetFileDescriptor
import android.content.res.AssetManager
import android.media.AudioAttributes
import android.media.AudioFocusRequest
import android.media.AudioManager
import android.media.MediaPlayer
import android.media.SoundPool
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import android.provider.Settings
import com.pathfindergod.spoke.data.local.AppPreferences
import kotlin.random.Random

const val PITCH_JITTER = 0.08f

private const val PITCH_HIGH = 1.10f
private const val PITCH_LOW = 0.90f
private const val MAX_CASCADE = 10
private const val CASCADE_STEP_MS = 55L
private const val CROSSFADE_STEPS = 12
private const val CROSSFADE_STEP_MS = 100L
private const val DUCK_STEPS = 4
private const val DUCK_STEP_MS = 40L
private const val DUCK_SCALE = 0.3f
private const val DUCK_HOLD_MS = 1200L

internal fun pitchForDie(sides: Int, random: Random = Random.Default): Float {
    val t = (sides.coerceIn(4, 20) - 4) / 16f
    val base = PITCH_HIGH + (PITCH_LOW - PITCH_HIGH) * t
    val jitter = random.nextFloat() * 2f * PITCH_JITTER - PITCH_JITTER
    return (base + jitter).coerceIn(0.5f, 2f)
}

enum class HapticPattern(val timings: LongArray, val amplitudes: IntArray) {
    LIGHT_TICK(longArrayOf(0L, 10L), intArrayOf(0, 80)),
    BUTTON_PRESS(longArrayOf(0L, 16L), intArrayOf(0, 140)),
    TAB_CHANGE(longArrayOf(0L, 12L, 24L, 14L), intArrayOf(0, 110, 0, 160)),
    IMPACT(longArrayOf(0L, 24L), intArrayOf(0, 210)),
    CRIT(longArrayOf(0L, 14L, 30L, 20L, 64L), intArrayOf(0, 255, 0, 255, 0)),
    FUMBLE(longArrayOf(0L, 66L, 36L, 28L), intArrayOf(0, 255, 0, 110)),
    DAMAGE(longArrayOf(0L, 30L, 26L, 16L), intArrayOf(0, 230, 0, 110)),
}

class AudioService(context: Context) {

    companion object {
        const val SFX_CLATTER = "audio/dice_roll.ogg"
        const val SFX_CRIT = "audio/dice_crit.wav"
        const val SFX_FAIL = "audio/dice_fail.ogg"
        const val SFX_ERROR = "audio/error.ogg"
        const val SFX_TAP = "audio/tap.wav"
        const val BGM_TAVERN = "audio/bgm_tavern.mp3"
        const val BGM_INN = "audio/bgm_inn.mp3"

        val BGM_TRACKS = listOf(BGM_TAVERN, BGM_INN)

        private val UI_PATHS = setOf(SFX_TAP, SFX_ERROR)
        private const val GAME_STREAMS = 6
        private const val UI_STREAMS = 3
        private const val MAX_PENDING = 24

        @Volatile
        private var shared: AudioService? = null

        fun get(context: Context): AudioService =
            shared ?: synchronized(this) {
                shared ?: AudioService(context).also { shared = it }
            }

        private fun resolveVibrator(context: Context): Vibrator? = try {
            if (Build.VERSION.SDK_INT >= 31) {
                context.getSystemService(VibratorManager::class.java)?.defaultVibrator
            } else {
                @Suppress("DEPRECATION")
                context.getSystemService(Context.VIBRATOR_SERVICE) as? Vibrator
            }
        } catch (_: Exception) {
            null
        }

        private fun openFd(assets: AssetManager, path: String): AssetFileDescriptor? = try {
            assets.openFd(path)
        } catch (_: Exception) {
            null
        }
    }

    private class Bank(
        private val assets: AssetManager,
        usage: Int,
        contentType: Int,
        streams: Int,
        private val onReady: (String) -> Unit,
    ) {
        private val ids = mutableMapOf<String, Int>()
        private val paths = mutableMapOf<Int, String>()
        private val ready = mutableSetOf<String>()
        private val pool: SoundPool

        init {
            pool = SoundPool.Builder()
                .setMaxStreams(streams)
                .setAudioAttributes(
                    AudioAttributes.Builder()
                        .setUsage(usage)
                        .setContentType(contentType)
                        .build(),
                )
                .build()
            pool.setOnLoadCompleteListener { _, sampleId, status ->
                val path = paths[sampleId] ?: return@setOnLoadCompleteListener
                if (status == 0) synchronized(ready) { ready += path }
                onReady(path)
            }
        }

        fun load(path: String): Int {
            ids[path]?.let { return it }
            val fd = openFd(assets, path) ?: return 0
            return try {
                val id = pool.load(fd, 1)
                if (id != 0) {
                    ids[path] = id
                    paths[id] = path
                }
                id
            } catch (_: Exception) {
                0
            } finally {
                fd.close()
            }
        }

        fun isReady(path: String): Boolean = synchronized(ready) { path in ready }

        fun play(path: String, volume: Float, pitch: Float): Int =
            ids[path]?.let { pool.play(it, volume, pitch, 1, 0, 1f) } ?: 0

        fun release() {
            ids.clear()
            paths.clear()
            synchronized(ready) { ready.clear() }
            pool.release()
        }
    }

    private val appContext = context.applicationContext
    private val prefs = AppPreferences(appContext)
    private val main = Handler(Looper.getMainLooper())
    private val audioManager = appContext.getSystemService(Context.AUDIO_SERVICE) as? AudioManager
    private val vibrator = resolveVibrator(appContext)
    private val pending = mutableListOf<Triple<String, Float, Float>>()

    private val game = Bank(
        assets = appContext.assets,
        usage = AudioAttributes.USAGE_GAME,
        contentType = AudioAttributes.CONTENT_TYPE_SONIFICATION,
        streams = GAME_STREAMS,
        onReady = ::drain,
    )

    private val ui = Bank(
        assets = appContext.assets,
        usage = AudioAttributes.USAGE_ASSISTANCE_SONIFICATION,
        contentType = AudioAttributes.CONTENT_TYPE_SONIFICATION,
        streams = UI_STREAMS,
        onReady = ::drain,
    )

    private var bgm: MediaPlayer? = null
    private var bgmTrack: String? = null
    private var bgmVolume = 1f
    private var focusRequest: AudioFocusRequest? = null
    private var generation = 0
    private var released = false

    private val focusChange = AudioManager.OnAudioFocusChangeListener { change ->
        when (change) {
            AudioManager.AUDIOFOCUS_LOSS -> {
                abandonFocus()
                stopBgm()
            }
            AudioManager.AUDIOFOCUS_LOSS_TRANSIENT -> pauseBgm()
            AudioManager.AUDIOFOCUS_LOSS_TRANSIENT_CAN_DUCK -> rampBgm(DUCK_SCALE)
            AudioManager.AUDIOFOCUS_GAIN -> {
                rampBgm(bgmVolume)
                bgm?.let { runCatching { it.start() } }
            }
            else -> Unit
        }
    }

    fun warmUp() {
        if (released) return
        listOf(SFX_CLATTER, SFX_CRIT, SFX_FAIL).forEach { game.load(it) }
        listOf(SFX_TAP, SFX_ERROR).forEach { ui.load(it) }
    }

    fun playClatter(sides: Int = 20, diceCount: Int = 1) {
        if (!sfxAllowed()) return
        val hits = diceCount.coerceIn(1, MAX_CASCADE)
        for (i in 0 until hits) {
            emit(
                path = SFX_CLATTER,
                volume = 1f - 0.55f * i / hits,
                pitch = pitchForDie(sides),
                bank = game,
                delayMs = i * CASCADE_STEP_MS,
            )
        }
        buzz(if (hits > 1) HapticPattern.IMPACT else HapticPattern.LIGHT_TICK)
        duckBgm()
    }

    fun playCritChime(sides: Int = 20) {
        emit(SFX_CRIT, 1f, pitchForDie(sides), game, 0L)
        buzz(HapticPattern.CRIT)
        duckBgm()
    }

    fun playFumble(sides: Int = 20) {
        emit(SFX_FAIL, 1f, pitchForDie(sides), game, 0L)
        buzz(HapticPattern.FUMBLE)
        duckBgm()
    }

    fun playError() {
        emit(SFX_ERROR, 1f, 1f, ui, 0L)
        buzz(HapticPattern.BUTTON_PRESS)
    }

    fun playTap() {
        emit(SFX_TAP, 0.7f, pitchForDie(6), ui, 0L)
    }

    fun buttonPress() {
        playTap()
        buzz(HapticPattern.BUTTON_PRESS)
    }

    fun tabChange() {
        playTap()
        buzz(HapticPattern.TAB_CHANGE)
    }

    fun impact() {
        buzz(HapticPattern.IMPACT)
    }

    fun damage() {
        emit(SFX_ERROR, 0.8f, 0.85f, ui, 0L)
        buzz(HapticPattern.DAMAGE)
    }

    fun playSfx(assetPath: String) {
        emit(assetPath, 1f, 1f, game, 0L)
    }

    fun buzz(pattern: HapticPattern) {
        if (released || !prefs.hapticsEnabled()) return
        val device = vibrator ?: return
        if (!device.hasVibrator() || !systemHapticsEnabled()) return
        runCatching {
            device.vibrate(VibrationEffect.createWaveform(pattern.timings, pattern.amplitudes, -1))
        }
    }

    fun syncMusic() {
        if (released) return
        val track = prefs.bgmTrack()
        when {
            !prefs.musicEnabled() -> stopBgm()
            track in BGM_TRACKS -> playBgm(track)
            else -> stopBgm()
        }
    }

    fun playBgm(track: String) {
        if (released) return
        if (!prefs.musicEnabled()) {
            stopBgm()
            return
        }
        val target = if (track in BGM_TRACKS) track else BGM_TAVERN
        if (bgmTrack == target && bgm != null) return
        val incoming = buildPlayer(target) ?: return
        requestFocus()
        generation++
        val token = generation
        bgmVolume = 1f
        incoming.setVolume(0f, 0f)
        incoming.start()
        val outgoing = bgm
        bgm = incoming
        bgmTrack = target
        for (i in 1..CROSSFADE_STEPS) {
            val f = i / CROSSFADE_STEPS.toFloat()
            main.postDelayed({
                if (released || token != generation) return@postDelayed
                runCatching { incoming.setVolume(f, f) }
                outgoing?.let { player ->
                    runCatching { player.setVolume(1f - f, 1f - f) }
                }
                if (i == CROSSFADE_STEPS) {
                    outgoing?.let { player ->
                        runCatching { player.stop() }
                        player.release()
                    }
                }
            }, CROSSFADE_STEP_MS * i)
        }
    }

    fun stopBgm() {
        generation++
        val player = bgm
        bgm = null
        bgmTrack = null
        player?.let { runCatching { it.stop() } }
        player?.release()
        abandonFocus()
    }

    fun release() {
        if (released) return
        released = true
        stopBgm()
        main.removeCallbacksAndMessages(null)
        synchronized(pending) { pending.clear() }
        game.release()
        ui.release()
        synchronized(Companion) { if (shared === this) shared = null }
    }

    private fun sfxAllowed(): Boolean = !released && prefs.sfxEnabled()

    private fun emit(path: String, volume: Float, pitch: Float, bank: Bank, delayMs: Long) {
        if (!sfxAllowed()) return
        bank.load(path)
        if (delayMs > 0L) {
            main.postDelayed({ fire(path, volume, pitch, bank) }, delayMs)
            return
        }
        fire(path, volume, pitch, bank)
    }

    private fun fire(path: String, volume: Float, pitch: Float, bank: Bank) {
        if (!sfxAllowed()) return
        if (!bank.isReady(path)) {
            synchronized(pending) {
                if (pending.size >= MAX_PENDING) pending.removeAt(0)
                pending += Triple(path, volume, pitch)
            }
            return
        }
        bank.play(path, volume, pitch)
    }

    private fun drain(path: String?) {
        val due = mutableListOf<Triple<String, Float, Float>>()
        synchronized(pending) {
            val kept = mutableListOf<Triple<String, Float, Float>>()
            for (entry in pending) {
                if (path == null || entry.first == path) due += entry else kept += entry
            }
            pending.clear()
            pending += kept
        }
        due.forEach { (p, volume, pitch) ->
            val bank = if (p in UI_PATHS) ui else game
            if (bank.isReady(p)) bank.play(p, volume, pitch)
        }
    }

    private fun rampBgm(target: Float) {
        val player = bgm ?: return
        val token = generation
        for (i in 1..DUCK_STEPS) {
            val f = i / DUCK_STEPS.toFloat()
            main.postDelayed({
                if (released || token != generation) return@postDelayed
                val level = bgmVolume * (1f - f) + target * f
                runCatching { player.setVolume(level, level) }
            }, DUCK_STEP_MS * i)
        }
        if (target > bgmVolume) {
            main.postDelayed({
                if (released || token != generation) return@postDelayed
                runCatching { player.setVolume(target, target) }
            }, DUCK_HOLD_MS)
        }
    }

    private fun duckBgm() {
        val player = bgm ?: return
        val token = generation
        for (i in 1..DUCK_STEPS) {
            val f = 1f - i / DUCK_STEPS.toFloat()
            main.postDelayed({
                if (released || token != generation) return@postDelayed
                runCatching { player.setVolume(bgmVolume * f, bgmVolume * f) }
            }, DUCK_STEP_MS * i)
        }
        main.postDelayed({
            if (released || token != generation) return@postDelayed
            runCatching { player.setVolume(bgmVolume, bgmVolume) }
        }, DUCK_HOLD_MS)
    }

    private fun pauseBgm() {
        bgm?.let { runCatching { it.pause() } }
    }

    private fun requestFocus() {
        val manager = audioManager ?: return
        val request = focusRequest ?: AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN)
            .setAudioAttributes(
                AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_MEDIA)
                    .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC)
                    .build(),
            )
            .setOnAudioFocusChangeListener(focusChange, main)
            .build()
            .also { focusRequest = it }
        runCatching { manager.requestAudioFocus(request) }
    }

    private fun abandonFocus() {
        val manager = audioManager ?: return
        focusRequest?.let { runCatching { manager.abandonAudioFocusRequest(it) } }
        focusRequest = null
    }

    private fun buildPlayer(path: String): MediaPlayer? {
        val fd = openFd(appContext.assets, path) ?: return null
        val player = MediaPlayer()
        return try {
            player.setAudioAttributes(
                AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_MEDIA)
                    .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC)
                    .build(),
            )
            player.setDataSource(fd.fileDescriptor, fd.startOffset, fd.length)
            player.isLooping = true
            player.prepare()
            player
        } catch (_: Exception) {
            player.release()
            null
        } finally {
            fd.close()
        }
    }

    private fun systemHapticsEnabled(): Boolean {
        val resolver = appContext.contentResolver
        val touch = runCatching {
            Settings.System.getInt(resolver, Settings.System.HAPTIC_FEEDBACK_ENABLED, 1)
        }.getOrDefault(1) != 0
        return touch
    }
}
