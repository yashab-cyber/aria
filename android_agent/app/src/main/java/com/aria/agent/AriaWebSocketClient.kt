package com.aria.agent

import android.content.Context
import android.os.Build
import android.util.Log
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import com.google.gson.Gson
import kotlinx.coroutines.*
import okhttp3.*
import java.util.concurrent.TimeUnit
import kotlin.math.min
import kotlin.math.pow

class AriaWebSocketClient(
    private val service: AriaAccessibilityService,
    private val commandHandler: CommandHandler
) {
    private val TAG = "ARIA_WS"
    
    private var webSocket: WebSocket? = null
    private val client = OkHttpClient.Builder()
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .pingInterval(30, TimeUnit.SECONDS)
        .build()
        
    private val gson = Gson()
    private var isConnected = false
    private var reconnectAttempt = 0
    private var reconnectJob: Job? = null
    
    fun connect() {
        if (isConnected) return
        
        val prefs = service.getSharedPreferences("aria_prefs", Context.MODE_PRIVATE)
        val url = prefs.getString("server_url", "") ?: ""
        
        if (url.isEmpty()) {
            Log.e(TAG, "No server URL configured")
            NotificationHelper.updateNotification(service, "Missing Server URL")
            return
        }
        
        Log.i(TAG, "Connecting to $url")
        NotificationHelper.updateNotification(service, "Connecting...")
        
        val request = Request.Builder().url(url).build()
        
        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                Log.i(TAG, "Connected to ARIA Server")
                isConnected = true
                reconnectAttempt = 0
                NotificationHelper.updateNotification(service, "Connected")
                sendRegistration()
            }
            
            override fun onMessage(webSocket: WebSocket, text: String) {
                Log.d(TAG, "Received message: $text")
                try {
                    val map = gson.fromJson(text, Map::class.java) as Map<String, Any>
                    val type = map["type"] as? String ?: return
                    
                    if (type == "ping") {
                        val timestamp = System.currentTimeMillis()
                        webSocket.send(gson.toJson(mapOf("type" to "pong", "timestamp" to timestamp)))
                        return
                    }
                    
                    val commandId = map["command_id"] as? String ?: return
                    
                    // Dispatch to handler in coroutine
                    service.serviceScope.launch(Dispatchers.IO) {
                        try {
                            val result = commandHandler.handleCommand(type, map)
                            sendResult(commandId, "ok", result)
                        } catch (e: Exception) {
                            Log.e(TAG, "Error handling command", e)
                            sendResult(commandId, "error", mapOf("message" to (e.message ?: "Unknown error")))
                        }
                    }
                } catch (e: Exception) {
                    Log.e(TAG, "Failed to parse message", e)
                }
            }
            
            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                Log.i(TAG, "WebSocket Closed: $reason")
                isConnected = false
                scheduleReconnect()
            }
            
            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                Log.e(TAG, "WebSocket Failure", t)
                isConnected = false
                scheduleReconnect()
            }
        })
    }
    
    private fun sendRegistration() {
        val prefs = service.getSharedPreferences("aria_prefs", Context.MODE_PRIVATE)
        val name = prefs.getString("device_name", Build.MODEL) ?: Build.MODEL
        
        val reg = mapOf(
            "type" to "register",
            "name" to name,
            "platform" to "android",
            "android_version" to Build.VERSION.RELEASE,
            "model" to Build.MODEL,
            "capabilities" to listOf(
                "tap", "swipe", "type_text", "key_event",
                "screenshot", "read_screen", "ui_dump",
                "open_app", "close_app", "list_apps",
                "read_file", "write_file", "list_files",
                "send_whatsapp", "read_whatsapp",
                "send_sms", "make_call",
                "get_battery", "get_wifi", "set_volume",
                "set_brightness", "get_clipboard", "set_clipboard",
                "send_notification", "open_url"
            )
        )
        webSocket?.send(gson.toJson(reg))
    }
    
    private fun sendResult(commandId: String, status: String, data: Map<String, Any?>) {
        val response = mapOf(
            "type" to "result",
            "command_id" to commandId,
            "status" to status,
            "data" to data
        )
        webSocket?.send(gson.toJson(response))
    }
    
    private fun scheduleReconnect() {
        reconnectJob?.cancel()
        reconnectJob = service.serviceScope.launch {
            val delaySeconds = min(60.0, 3.0 * (1.5).pow(reconnectAttempt)).toLong()
            Log.i(TAG, "Scheduling reconnect in $delaySeconds seconds")
            NotificationHelper.updateNotification(service, "Reconnecting in ${delaySeconds}s...")
            delay(delaySeconds * 1000)
            reconnectAttempt++
            connect()
        }
    }
    
    fun disconnect() {
        reconnectJob?.cancel()
        webSocket?.close(1000, "Service shutting down")
        isConnected = false
    }
}
