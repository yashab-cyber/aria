package com.aria.agent

import android.Manifest
import android.annotation.SuppressLint
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.SharedPreferences
import android.content.pm.PackageManager
import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioTrack
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.view.MotionEvent
import android.view.View
import android.widget.EditText
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import com.google.android.material.button.MaterialButton
import com.google.android.material.floatingactionbutton.FloatingActionButton

class MainActivity : AppCompatActivity() {

    private lateinit var etServerUrl: EditText
    private lateinit var etAuthToken: EditText
    private lateinit var etDeviceName: EditText
    private lateinit var btnSave: MaterialButton
    private lateinit var btnAccessibility: MaterialButton
    private lateinit var tvStatus: TextView
    private lateinit var layoutSettingsInputs: LinearLayout
    private lateinit var btnToggleSettings: ImageView
    private lateinit var prefs: SharedPreferences

    private lateinit var rvChat: RecyclerView
    private lateinit var etChatInput: EditText
    private lateinit var btnSend: FloatingActionButton
    private lateinit var btnMic: FloatingActionButton

    private lateinit var chatAdapter: ChatAdapter
    private var chatClient: ChatWebSocketClient? = null
    private var audioHelper: AudioRecorderHelper? = null
    private var audioTrack: AudioTrack? = null

    private var isSettingsExpanded = false

    private val statusReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent) {
            val status = intent.getStringExtra("status") ?: return
            tvStatus.text = status
            when {
                status.contains("Connected", true) -> tvStatus.setTextColor(ContextCompat.getColor(context, R.color.colorConnected))
                status.contains("Disconnected", true) || status.contains("Error", true) -> tvStatus.setTextColor(ContextCompat.getColor(context, R.color.colorDisconnected))
                else -> tvStatus.setTextColor(ContextCompat.getColor(context, R.color.colorReconnecting))
            }
        }
    }

    @SuppressLint("ClickableViewAccessibility")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        initViews()
        initPrefs()
        initRecyclerView()
        
        // Start WorkManager for periodic reconnects
        val request = androidx.work.PeriodicWorkRequestBuilder<ReconnectWorker>(15, java.util.concurrent.TimeUnit.MINUTES)
            .setConstraints(androidx.work.Constraints.Builder().setRequiredNetworkType(androidx.work.NetworkType.CONNECTED).build())
            .build()
        androidx.work.WorkManager.getInstance(this).enqueueUniquePeriodicWork(
            "aria_reconnect", androidx.work.ExistingPeriodicWorkPolicy.KEEP, request
        )

        // Request Permissions
        val perms = mutableListOf<String>()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            perms.add(Manifest.permission.POST_NOTIFICATIONS)
        }
        perms.add(Manifest.permission.RECORD_AUDIO)
        
        val missing = perms.filter { ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED }
        if (missing.isNotEmpty()) {
            ActivityCompat.requestPermissions(this, missing.toTypedArray(), 100)
        }

        btnToggleSettings.setOnClickListener {
            isSettingsExpanded = !isSettingsExpanded
            layoutSettingsInputs.visibility = if (isSettingsExpanded) View.VISIBLE else View.GONE
            btnToggleSettings.rotation = if (isSettingsExpanded) 180f else 0f
        }

        btnSave.setOnClickListener {
            saveSettings()
            connectClients()
            // Tell accessibility service to reconnect its websocket
            sendBroadcast(Intent("com.aria.agent.RECONNECT"))
        }

        btnAccessibility.setOnClickListener {
            startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
        }

        btnSend.setOnClickListener {
            val text = etChatInput.text.toString().trim()
            if (text.isNotEmpty()) {
                chatAdapter.addUserMessage(text)
                chatClient?.sendMessage(text)
                etChatInput.text.clear()
                rvChat.smoothScrollToPosition(chatAdapter.itemCount - 1)
            }
        }

        btnMic.setOnTouchListener { _, event ->
            when (event.action) {
                MotionEvent.ACTION_DOWN -> {
                    btnMic.imageTintList = ContextCompat.getColorStateList(this, R.color.colorDisconnected)
                    audioHelper?.startRecording()
                    true
                }
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                    btnMic.imageTintList = ContextCompat.getColorStateList(this, R.color.colorAccent)
                    audioHelper?.stopRecording()
                    true
                }
                else -> false
            }
        }

        // Auto-connect on open if settings exist
        if (prefs.getString("server_url", "")?.isNotBlank() == true) {
            connectClients()
        } else {
            isSettingsExpanded = true
            layoutSettingsInputs.visibility = View.VISIBLE
            btnToggleSettings.rotation = 180f
        }
    }

    private fun initViews() {
        etServerUrl = findViewById(R.id.etServerUrl)
        etAuthToken = findViewById(R.id.etAuthToken)
        etDeviceName = findViewById(R.id.etDeviceName)
        btnSave = findViewById(R.id.btnSave)
        btnAccessibility = findViewById(R.id.btnAccessibility)
        tvStatus = findViewById(R.id.tvStatus)
        layoutSettingsInputs = findViewById(R.id.layoutSettingsInputs)
        btnToggleSettings = findViewById(R.id.btnToggleSettings)
        
        rvChat = findViewById(R.id.rvChat)
        etChatInput = findViewById(R.id.etChatInput)
        btnSend = findViewById(R.id.btnSend)
        btnMic = findViewById(R.id.btnMic)
    }

    private fun initPrefs() {
        val masterKey = MasterKey.Builder(this)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()
            
        prefs = EncryptedSharedPreferences.create(
            this, "aria_prefs", masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
        )

        etServerUrl.setText(prefs.getString("server_url", "ws://192.168.1.100:8000/ws/device"))
        etAuthToken.setText(prefs.getString("auth_token", ""))
        etDeviceName.setText(prefs.getString("device_name", Build.MODEL))
    }

    private fun initRecyclerView() {
        chatAdapter = ChatAdapter()
        val layoutManager = LinearLayoutManager(this)
        layoutManager.stackFromEnd = true
        rvChat.layoutManager = layoutManager
        rvChat.adapter = chatAdapter
    }

    private fun saveSettings() {
        prefs.edit()
            .putString("server_url", etServerUrl.text.toString())
            .putString("auth_token", etAuthToken.text.toString())
            .putString("device_name", etDeviceName.text.toString())
            .apply()
    }

    private fun connectClients() {
        chatClient?.disconnect()
        audioHelper?.disconnect()

        val url = prefs.getString("server_url", "") ?: return
        val token = prefs.getString("auth_token", "") ?: ""
        // Map /ws/device to /ws for the chat client
        val chatUrl = url.replace("/ws/device", "/ws")

        chatClient = ChatWebSocketClient(chatUrl, token, 
            onMessage = { chunk ->
                chatAdapter.addOrUpdateAriaChunk(chunk)
                rvChat.smoothScrollToPosition(chatAdapter.itemCount - 1)
            },
            onStatusChange = { }
        )
        chatClient?.connect()

        audioHelper = AudioRecorderHelper(this, chatUrl, token, 
            onAudioResponse = { bytes -> playAudio(bytes) }
        )
        audioHelper?.connect()
    }

    private fun playAudio(bytes: ByteArray) {
        if (audioTrack == null || audioTrack?.state == AudioTrack.STATE_UNINITIALIZED) {
            val format = AudioFormat.Builder()
                .setSampleRate(16000)
                .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                .build()
                
            val attributes = AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_MEDIA)
                .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                .build()
                
            val minSize = AudioTrack.getMinBufferSize(16000, AudioFormat.CHANNEL_OUT_MONO, AudioFormat.ENCODING_PCM_16BIT)
            
            audioTrack = AudioTrack.Builder()
                .setAudioAttributes(attributes)
                .setAudioFormat(format)
                .setBufferSizeInBytes(minSize)
                .setTransferMode(AudioTrack.MODE_STREAM)
                .build()
        }
        
        try {
            audioTrack?.play()
            audioTrack?.write(bytes, 0, bytes.size)
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    override fun onResume() {
        super.onResume()
        val filter = IntentFilter("com.aria.agent.STATUS_UPDATE")
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(statusReceiver, filter, Context.RECEIVER_NOT_EXPORTED)
        } else {
            registerReceiver(statusReceiver, filter)
        }
    }

    override fun onPause() {
        super.onPause()
        unregisterReceiver(statusReceiver)
    }

    override fun onDestroy() {
        chatClient?.disconnect()
        audioHelper?.disconnect()
        audioTrack?.release()
        super.onDestroy()
    }
}
