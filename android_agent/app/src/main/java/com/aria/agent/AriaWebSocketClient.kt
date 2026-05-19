package com.aria.agent

import android.content.Context
import android.os.Build
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import kotlinx.coroutines.*
import okhttp3.*
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.TimeUnit
import kotlin.math.min

class AriaWebSocketClient(
    private val context: Context,
    private val onCommand: suspend (JSONObject) -> JSONObject,
    private val onStatusChange: (String) -> Unit
) {
    private var webSocket: WebSocket? = null
    private var isConnected: Boolean = false
    private var retryDelayMs: Long = 3000
    private val maxRetryDelayMs: Long = 60000
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    fun connect() {
        val masterKey = MasterKey.Builder(context)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()
        val prefs = EncryptedSharedPreferences.create(
            context, "aria_prefs", masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
        )

        val url = prefs.getString("server_url", "") ?: ""
        val token = prefs.getString("auth_token", "") ?: ""
        val deviceName = prefs.getString("device_name", Build.MODEL) ?: Build.MODEL

        if (url.isBlank()) {
            onStatusChange("No server URL configured")
            return
        }

        val client = OkHttpClient.Builder()
            .connectTimeout(10, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .build()

        val request = Request.Builder()
            .url(url)
            .addHeader("X-Token", token)
            .build()

        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                isConnected = true
                retryDelayMs = 3000
                onStatusChange("Connected")

                val capabilities = JSONArray(listOf(
                    "tap", "tap_by_text", "tap_by_id", "long_press", "swipe", "type_text", "clear_text", "key_event", "scroll",
                    "screenshot", "read_screen", "ui_dump", "find_element",
                    "open_app", "close_app", "list_apps", "get_current_app", "open_url",
                    "send_whatsapp", "read_whatsapp", "whatsapp_send_file",
                    "read_file", "write_file", "list_files", "delete_file",
                    "get_battery", "get_wifi", "get_clipboard", "set_clipboard", "send_notification", "set_volume", "send_sms", "make_call",
                    "media_play_pause", "media_next", "media_previous", "set_brightness"
                ))

                val reg = JSONObject().apply {
                    put("type", "register")
                    put("name", deviceName)
                    put("platform", "android")
                    put("android_version", Build.VERSION.RELEASE)
                    put("model", Build.MODEL)
                    put("manufacturer", Build.MANUFACTURER)
                    put("capabilities", capabilities)
                }
                webSocket.send(reg.toString())

                // Heartbeat
                scope.launch {
                    while (isConnected) {
                        delay(30000)
                        val ping = JSONObject().apply {
                            put("type", "ping")
                            put("timestamp", System.currentTimeMillis())
                        }
                        webSocket.send(ping.toString())
                    }
                }
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                scope.launch {
                    try {
                        val json = JSONObject(text)
                        if (json.optString("type") == "ping") {
                            val pong = JSONObject().apply {
                                put("type", "pong")
                                put("timestamp", System.currentTimeMillis())
                            }
                            webSocket.send(pong.toString())
                        } else {
                            val result = onCommand(json)
                            webSocket.send(result.toString())
                        }
                    } catch (e: Exception) {
                        // ignore malformed JSON
                    }
                }
            }

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                isConnected = false
                onStatusChange("Disconnected")
                scheduleReconnect()
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                isConnected = false
                onStatusChange("Disconnected")
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                isConnected = false
                onStatusChange("Error: ${t.message}")
                scheduleReconnect()
            }
        })
    }

    private fun scheduleReconnect() {
        scope.launch {
            onStatusChange("Reconnecting in ${retryDelayMs / 1000}s...")
            delay(retryDelayMs)
            retryDelayMs = min((retryDelayMs * 1.5).toLong(), maxRetryDelayMs)
            connect()
        }
    }

    fun disconnect() {
        webSocket?.close(1000, "User disconnect")
        scope.cancel()
        isConnected = false
    }

    fun isConnected(): Boolean = isConnected
}
