// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.service

import android.content.Context
import android.content.res.AssetFileDescriptor
import android.media.AudioAttributes
import android.media.MediaPlayer
import android.media.SoundPool

class AudioService(context: Context) {

    companion object {
        const val SFX_CLATTER = "audio/dice_roll.ogg"
        const val SFX_CRIT = "audio/dice_crit.wav"
        const val BGM_TAVERN = "audio/bgm_tavern.mp3"
        const val BGM_INN = "audio/bgm_inn.mp3"
    }

    private val assets = context.assets
    private val pool: SoundPool = SoundPool.Builder()
        .setMaxStreams(4)
        .setAudioAttributes(
            AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_GAME)
                .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                .build(),
        )
        .build()
    private val sfxIds = mutableMapOf<String, Int>()
    private val loops = mutableMapOf<String, MediaPlayer>()
    private var released = false

    fun playClatter() {
        playSfx(SFX_CLATTER)
    }

    fun playCritChime() {
        playSfx(SFX_CRIT)
    }

    fun playSfx(assetPath: String) {
        if (released) return
        val id = sfxIds.getOrPut(assetPath) { loadSfx(assetPath) }
        if (id != 0) pool.play(id, 1f, 1f, 1, 0, 1f)
    }

    fun startLoop(assetPath: String) {
        if (released || loops.containsKey(assetPath)) return
        openFd(assetPath)?.let { fd ->
            val player = MediaPlayer()
            try {
                player.setDataSource(fd.fileDescriptor, fd.startOffset, fd.length)
                player.isLooping = true
                player.prepare()
                player.start()
                loops[assetPath] = player
            } catch (_: Exception) {
                player.release()
            } finally {
                fd.close()
            }
        }
    }

    fun stopLoop(assetPath: String) {
        loops.remove(assetPath)?.let {
            try {
                it.stop()
            } catch (_: Exception) {
            }
            it.release()
        }
    }

    fun release() {
        released = true
        loops.keys.toList().forEach { stopLoop(it) }
        pool.release()
    }

    private fun loadSfx(assetPath: String): Int {
        openFd(assetPath)?.let { fd ->
            try {
                return pool.load(fd, 1)
            } catch (_: Exception) {
            } finally {
                fd.close()
            }
        }
        return 0
    }

    private fun openFd(assetPath: String): AssetFileDescriptor? = try {
        assets.openFd(assetPath)
    } catch (_: Exception) {
        null
    }
}
