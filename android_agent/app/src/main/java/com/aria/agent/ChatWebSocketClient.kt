package com.aria.agent

import android.os.Handler
import android.os.Looper
import kotlinx.coroutines.*
import okhttp3.*
import org.json.JSONObject
import java.util.concurrent.TimeUnit

class ChatWebSocketClient(
    private val url: String,
    private val token: String,
    private val onMessage: (String) -> Unit,
    private val onStatusChange: (String) -> Unit
) {
    private var webSocket: WebSocket? = null
    private var isConnected: Boolean = false
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private val mainHandler = Handler(Looper.getMainLooper())

    fun connect() {
        if (url.isBlank()) return

        val client = OkHttpClient.Builder()
            .connectTimeout(10, TimeUnit.SECONDS)
            .readTimeout(0, TimeUnit.SECONDS) // 0 means no timeout for streaming
            .build()

        val request = Request.Builder()
            .url(url)
            .addHeader("X-Token", token)
            .build()

        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                isConnected = true
                postMain { onStatusChange("Connected to Chat") }
                
                // Keep-alive ping
                scope.launch {
                    while (isConnected) {
                        delay(30000)
                        try {
                            webSocket.send(JSONObject().put("type", "ping").toString())
                        } catch (e: Exception) {}
                    }
                }
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                try {
                    val json = JSONObject(text)
                    when (json.optString("type")) {
                        "chunk" -> {
                            val content = json.optString("content")
                            postMain { onMessage(content) }
                        }
                        "transcription" -> {
                            // Can show transcription if needed
                        }
                        "done" -> {
                            postMain { onMessage("<DONE>") }
                        }
                    }
                } catch (e: Exception) {
                    // Ignore malformed
                }
            }

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                isConnected = false
                postMain { onStatusChange("Disconnected") }
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                isConnected = false
                postMain { onStatusChange("Error: ${t.message}") }
            }
        })
    }

    fun sendMessage(text: String) {
        if (isConnected) {
            val json = JSONObject().apply {
                put("type", "message")
                put("text", text)
            }
            webSocket?.send(json.toString())
        }
    }

    fun disconnect() {
        webSocket?.close(1000, "User closed")
        isConnected = false
        scope.cancel()
    }

    private fun postMain(runnable: () -> Unit) {
        mainHandler.post(runnable)
    }
}
