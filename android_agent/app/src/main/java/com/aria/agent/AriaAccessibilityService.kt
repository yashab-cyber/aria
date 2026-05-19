package com.aria.agent

import android.accessibilityservice.AccessibilityService
import android.app.NotificationManager
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.Build
import android.view.accessibility.AccessibilityEvent
import kotlinx.coroutines.*
import org.json.JSONObject

class AriaAccessibilityService : AccessibilityService() {
    
    private lateinit var wsClient: AriaWebSocketClient
    private lateinit var commandHandler: CommandHandler
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    var currentPackage: String = ""
    var currentActivity: String = ""

    private val reconnectReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            if (intent?.action == "com.aria.agent.RECONNECT") {
                scope.launch {
                    wsClient.disconnect()
                    delay(500)
                    wsClient.connect()
                }
            }
        }
    }

    override fun onServiceConnected() {
        super.onServiceConnected()
        
        NotificationHelper.createChannel(this)
        val notification = NotificationHelper.buildNotification(this, "Starting...")
        startForeground(NotificationHelper.NOTIFICATION_ID, notification)
        
        commandHandler = CommandHandler(this)
        wsClient = AriaWebSocketClient(
            context = this,
            onCommand = { json -> commandHandler.handle(json) },
            onStatusChange = { status ->
                updateNotification(status)
                broadcastStatus(status)
            }
        )
        scope.launch { wsClient.connect() }
        
        val filter = IntentFilter("com.aria.agent.RECONNECT")
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(reconnectReceiver, filter, Context.RECEIVER_NOT_EXPORTED)
        } else {
            registerReceiver(reconnectReceiver, filter)
        }
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        if (event?.eventType == AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED) {
            currentPackage = event.packageName?.toString() ?: ""
            currentActivity = event.className?.toString() ?: ""
        }
    }

    override fun onInterrupt() {}

    override fun onDestroy() {
        try {
            unregisterReceiver(reconnectReceiver)
        } catch (e: Exception) {
            // Ignore if not registered
        }
        wsClient.disconnect()
        scope.cancel()
        super.onDestroy()
    }

    private fun updateNotification(status: String) {
        val notification = NotificationHelper.buildNotification(this, status)
        val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.notify(NotificationHelper.NOTIFICATION_ID, notification)
    }

    private fun broadcastStatus(status: String) {
        val intent = Intent("com.aria.agent.STATUS_UPDATE")
        intent.putExtra("status", status)
        sendBroadcast(intent)
    }
}
