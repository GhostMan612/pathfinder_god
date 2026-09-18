// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================

package com.pathfindergod.spoke.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Binder
import android.os.IBinder
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat
import com.pathfindergod.spoke.data.local.NetworkPreferences
import com.pathfindergod.spoke.data.network.HubWebSocketClient
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

enum class HubConnectionStatus {
    DISCONNECTED,
    CONNECTING,
    CONNECTED,
    RETRYING,
}

class HubForegroundService : Service() {
    private val binder = HubBinder()
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val client = HubWebSocketClient()
    private var streamUrl: String = DEFAULT_STREAM_URL
    private var linkJob: Job? = null

    inner class HubBinder : Binder() {
        fun getService(): HubForegroundService = this@HubForegroundService
    }

    override fun onBind(intent: Intent?): IBinder = binder

    override fun onCreate() {
        super.onCreate()
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(
            NotificationChannel(
                CHANNEL_ID,
                "Hub Link",
                NotificationManager.IMPORTANCE_LOW,
            ),
        )
        ServiceCompat.startForeground(
            this,
            NOTIFICATION_ID,
            buildNotification("Hub link idle"),
            ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC,
        )
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_CONNECT -> {
                streamUrl = intent.getStringExtra(EXTRA_URL)
                    ?: NetworkPreferences(this).streamUrl()
                maintainLink()
            }
            ACTION_DISCONNECT -> dropLink()
        }
        return START_STICKY
    }

    override fun onDestroy() {
        dropLink()
        scope.cancel()
        super.onDestroy()
    }

    fun send(text: String): Boolean = client.send(text)

    private fun buildNotification(status: String): Notification =
        NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Pathfinder God")
            .setContentText(status)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setOngoing(true)
            .build()

    private fun maintainLink() {
        if (linkJob?.isActive == true) return
        linkJob = scope.launch {
            var backoff = INITIAL_BACKOFF_MS
            while (true) {
                _status.value = HubConnectionStatus.CONNECTING
                try {
                    var first = true
                    client.stream(streamUrl).collect { message ->
                        if (first) {
                            first = false
                            backoff = INITIAL_BACKOFF_MS
                            _status.value = HubConnectionStatus.CONNECTED
                        }
                        _events.emit(message)
                    }
                } catch (_: Exception) {
                }
                _status.value = HubConnectionStatus.RETRYING
                delay(backoff)
                backoff = (backoff * 2).coerceAtMost(MAX_BACKOFF_MS)
            }
        }
    }

    private fun dropLink() {
        linkJob?.cancel()
        linkJob = null
        client.close()
        _status.value = HubConnectionStatus.DISCONNECTED
    }

    companion object {
        const val CHANNEL_ID = "pathfinder_hub_channel"
        const val ACTION_CONNECT = "com.pathfindergod.spoke.CONNECT"
        const val ACTION_DISCONNECT = "com.pathfindergod.spoke.DISCONNECT"
        const val EXTRA_URL = "stream_url"
        const val DEFAULT_STREAM_URL = "ws://10.0.2.2:8000/stream"

        private const val NOTIFICATION_ID = 1
        private const val INITIAL_BACKOFF_MS = 400L
        private const val MAX_BACKOFF_MS = 30_000L

        private val _status =
            MutableStateFlow(HubConnectionStatus.DISCONNECTED)
        val status: StateFlow<HubConnectionStatus> = _status.asStateFlow()

        private val _events = MutableSharedFlow<String>(extraBufferCapacity = 64)
        val events: SharedFlow<String> = _events.asSharedFlow()
    }
}
