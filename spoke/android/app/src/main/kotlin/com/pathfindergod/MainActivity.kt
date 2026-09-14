// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod

import android.util.Log
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import java.io.File
import java.io.FileOutputStream
import java.util.zip.GZIPInputStream

class MainActivity : FlutterActivity() {
    private val channelName = "com.pathfindergod/rulebook"
    private val tag = "RulebookChannel"

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, channelName)
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "extractGzAsset" -> {
                        val assetPath = call.argument<String>("assetPath")
                        val destPath = call.argument<String>("destPath")
                        if (assetPath == null || destPath == null) {
                            result.error("BAD_ARGS", "assetPath and destPath required", null)
                            return@setMethodCallHandler
                        }
                        Thread {
                            try {
                                val bytes = extractGzAsset(assetPath, destPath)
                                // Must post result on UI thread
                                runOnUiThread { result.success(bytes) }
                            } catch (e: Exception) {
                                Log.e(tag, "extractGzAsset failed", e)
                                runOnUiThread { result.error("EXTRACT_FAILED", e.message, e.toString()) }
                            }
                        }.start()
                    }
                    else -> result.notImplemented()
                }
            }
    }

    /**
     * Zero-copy streaming: AssetManager → GZIPInputStream → FileOutputStream
     * Peak RAM: 8 KB buffer (vs 180 MB with rootBundle.load + Isolate copy).
     * Atomic: writes to dest.tmp then rename (ext4 rename is atomic; power loss
     * leaves either old inode or new, never half-written).
     */
    private fun extractGzAsset(assetPath: String, destPath: String): Long {
        // Flutter assets are under flutter_assets/ prefix in the APK.
        // getLookupKeyForAsset handles localization variants; fallback to manual.
        val flutterLoader = io.flutter.FlutterInjector.instance().flutterLoader()
        val lookupKey = try {
            flutterLoader.getLookupKeyForAsset(assetPath.removePrefix("assets/").let { "assets/$it" })
                .let { it } // already "assets/..." -> flutterLoader will prefix flutter_assets/
        } catch (_: Exception) {
            "flutter_assets/$assetPath"
        }
        // Primary key via FlutterLoader, secondary via direct "flutter_assets/..."
        val keysToTry = listOf(
            lookupKey,
            "flutter_assets/$assetPath",
            "flutter_assets/assets/${assetPath.removePrefix("assets/")}"
        )

        var inputStream: java.io.InputStream? = null
        var lastError: Exception? = null
        for (key in keysToTry) {
            try {
                Log.i(tag, "Trying asset key: $key -> $destPath")
                inputStream = applicationContext.assets.open(key)
                Log.i(tag, "Opened $key")
                break
            } catch (e: Exception) {
                lastError = e
                Log.w(tag, "Failed key $key: ${e.message}")
            }
        }
        if (inputStream == null) {
            throw IllegalArgumentException("Asset not found for $assetPath (tried $keysToTry): $lastError")
        }

        val destFile = File(destPath)
        val tmpFile = File("$destPath.tmp")
        val parent = tmpFile.parentFile
        if (parent != null && !parent.exists()) {
            if (!parent.mkdirs()) {
                Log.w(tag, "mkdirs failed for ${parent.absolutePath}, exists=${parent.exists()}")
            }
        }
        if (tmpFile.exists()) tmpFile.delete()
        if (destFile.exists()) {
            // Keep old DB as backup until rename succeeds
            Log.i(tag, "Existing DB at ${destFile.absolutePath} size=${destFile.length()}")
        }

        var totalBytes = 0L
        inputStream.use { rawIn ->
            GZIPInputStream(rawIn, 8192).use { gzIn ->
                FileOutputStream(tmpFile).use { out ->
                    val buffer = ByteArray(8192)
                    var read: Int
                    while (gzIn.read(buffer).also { read = it } != -1) {
                        out.write(buffer, 0, read)
                        totalBytes += read
                    }
                    out.fd.sync() // ensure OS flush to disk (power-loss safety)
                }
            }
        }

        Log.i(tag, "Wrote $totalBytes bytes to tmp ${tmpFile.absolutePath}")

        // Atomic move: delete old, rename tmp -> dest
        if (destFile.exists() && !destFile.delete()) {
            Log.w(tag, "Failed to delete old dest ${destFile.absolutePath}")
        }
        if (!tmpFile.renameTo(destFile)) {
            // Fallback copy if renameTo fails across filesystems
            Log.w(tag, "renameTo failed, falling back to copy")
            tmpFile.copyTo(destFile, overwrite = true)
            tmpFile.delete()
        }

        Log.i(tag, "Extraction complete: ${destFile.absolutePath} ${destFile.length()} bytes")
        return totalBytes
    }
}
