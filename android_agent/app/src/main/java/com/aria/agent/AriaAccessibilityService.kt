package com.aria.agent

import android.accessibilityservice.AccessibilityService
import android.content.Intent
import android.view.accessibility.AccessibilityEvent
import android.view.KeyEvent
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel

class AriaAccessibilityService : AccessibilityService() {
    
    companion object {
        var instance: AriaAccessibilityService? = null
            private set
    }
    
    private val serviceJob = SupervisorJob()
    val serviceScope = CoroutineScope(Dispatchers.Main + serviceJob)
    
    lateinit var webSocketClient: AriaWebSocketClient
    lateinit var commandHandler: CommandHandler
    
    var currentActivePackage: String = ""
    var currentActiveActivity: String = ""

    override fun onServiceConnected() {
        super.onServiceConnected()
        instance = this
        
        NotificationHelper.createNotificationChannel(this)
        startForeground(NotificationHelper.NOTIFICATION_ID, NotificationHelper.buildNotification(this, "Connected"))
        
        commandHandler = CommandHandler(this)
        webSocketClient = AriaWebSocketClient(this, commandHandler)
        webSocketClient.connect()
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        if (event == null) return
        
        // Track the current active app package
        if (event.eventType == AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED) {
            event.packageName?.let { currentActivePackage = it.toString() }
            event.className?.let { currentActiveActivity = it.toString() }
        }
    }

    override fun onInterrupt() {
        // Accessibility service interrupted
    }

    override fun onUnbind(intent: Intent?): Boolean {
        instance = null
        webSocketClient.disconnect()
        serviceScope.cancel()
        return super.onUnbind(intent)
    }
    
    // Allow executors to inject key events directly
    fun injectKeyEvent(event: KeyEvent): Boolean {
        // Depending on Android version, filtering key events requires specific APIs.
        // We will fallback to shell command input if needed by executors.
        // But for standard global actions, we use performGlobalAction
        return false
    }
}
