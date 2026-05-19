package com.aria.agent

import android.content.Context
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import kotlinx.coroutines.*
import okhttp3.*
import okio.ByteString.Companion.toByteString
import java.util.concurrent.TimeUnit

class AudioRecorderHelper(
    private val context: Context,
    private val url: String,
    private val token: String,
    private val onAudioResponse: (ByteArray) -> Unit
) {
    private var webSocket: WebSocket? = null
    private var isRecording = false
    private var audioRecord: AudioRecord? = null
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    
    // Standard configuration for speech recognition (PCM 16-bit, 16kHz)
    private val sampleRate = 16000
    private val channelConfig = AudioFormat.CHANNEL_IN_MONO
    private val audioFormat = AudioFormat.ENCODING_PCM_16BIT
    private val bufferSize = AudioRecord.getMinBufferSize(sampleRate, channelConfig, audioFormat)

    fun connect() {
        if (url.isBlank()) return
        val audioUrl = url.replace("/ws/device", "/ws/audio").replace("/ws", "/ws/audio")
        
        val client = OkHttpClient.Builder().readTimeout(0, TimeUnit.SECONDS).build()
        val request = Request.Builder().url(audioUrl).addHeader("X-Token", token).build()

        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onMessage(webSocket: WebSocket, bytes: okio.ByteString) {
                // Backend sent audio bytes back (TTS response)
                onAudioResponse(bytes.toByteArray())
            }
            
            override fun onMessage(webSocket: WebSocket, text: String) {
                // Ignore text messages on audio socket (except transcription events if needed)
            }
        })
    }

    fun startRecording() {
        if (isRecording) return
        
        try {
            audioRecord = AudioRecord(
                MediaRecorder.AudioSource.MIC,
                sampleRate,
                channelConfig,
                audioFormat,
                bufferSize
            )
            
            audioRecord?.startRecording()
            isRecording = true
            
            scope.launch {
                val buffer = ByteArray(bufferSize)
                while (isRecording) {
                    val read = audioRecord?.read(buffer, 0, buffer.size) ?: 0
                    if (read > 0 && webSocket != null) {
                        // Send raw PCM stream. Note: backend process_webm_to_text expects WEBM,
                        // so we might need to rely on the backend converting raw PCM or we send a WEBM file on stop.
                        // For a live stream, PCM bytes are standard. We will send bytes.
                        webSocket?.send(buffer.copyOfRange(0, read).toByteString())
                    }
                }
            }
        } catch (e: SecurityException) {
            // Permission not granted
        }
    }

    fun stopRecording() {
        isRecording = false
        audioRecord?.stop()
        audioRecord?.release()
        audioRecord = null
    }

    fun disconnect() {
        stopRecording()
        webSocket?.close(1000, "App closed")
        scope.cancel()
    }
}
