package com.aria.agent

import android.Manifest
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.SharedPreferences
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.concurrent.TimeUnit

class SettingsActivity : AppCompatActivity() {

    private lateinit var etServerUrl: EditText
    private lateinit var etDeviceName: EditText
    private lateinit var etToken: EditText
    private lateinit var btnSave: Button
    private lateinit var btnAccessibility: Button
    private lateinit var tvStatus: TextView
    private lateinit var tvLogs: TextView
    private val logLines = mutableListOf<String>()
    private lateinit var prefs: SharedPreferences

    private val statusReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent) {
            val status = intent.getStringExtra("status") ?: return
            tvStatus.text = status
            
            when {
                status.contains("Connected", true) -> tvStatus.setTextColor(ContextCompat.getColor(context, R.color.colorConnected))
                status.contains("Disconnected", true) || status.contains("Error", true) -> tvStatus.setTextColor(ContextCompat.getColor(context, R.color.colorDisconnected))
                else -> tvStatus.setTextColor(ContextCompat.getColor(context, R.color.colorReconnecting))
            }
            addLog(status)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        etServerUrl = findViewById(R.id.etServerUrl)
        etDeviceName = findViewById(R.id.etDeviceName)
        etToken = findViewById(R.id.etToken)
        btnSave = findViewById(R.id.btnSave)
        btnAccessibility = findViewById(R.id.btnAccessibility)
        tvStatus = findViewById(R.id.tvStatus)
        tvLogs = findViewById(R.id.tvLogs)

        val masterKey = MasterKey.Builder(this)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()
            
        prefs = EncryptedSharedPreferences.create(
            this, "aria_prefs", masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
        )

        etServerUrl.setText(prefs.getString("server_url", "ws://192.168.1.100:8000/ws/device"))
        etDeviceName.setText(prefs.getString("device_name", Build.MODEL))
        etToken.setText(prefs.getString("auth_token", ""))

        btnSave.setOnClickListener {
            prefs.edit()
                .putString("server_url", etServerUrl.text.toString())
                .putString("device_name", etDeviceName.text.toString())
                .putString("auth_token", etToken.text.toString())
                .apply()
                
            addLog("Settings saved. Reconnecting...")
            sendBroadcast(Intent("com.aria.agent.RECONNECT"))
        }

        btnAccessibility.setOnClickListener {
            startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.POST_NOTIFICATIONS), 100)
            }
        }

        val request = PeriodicWorkRequestBuilder<ReconnectWorker>(15, TimeUnit.MINUTES)
            .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
            .build()
        WorkManager.getInstance(this).enqueueUniquePeriodicWork(
            "aria_reconnect", ExistingPeriodicWorkPolicy.KEEP, request
        )
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

    private fun addLog(line: String) {
        val timestamp = SimpleDateFormat("HH:mm:ss", Locale.US).format(Date())
        logLines.add("[$timestamp] $line")
        if (logLines.size > 20) logLines.removeAt(0)
        tvLogs.text = logLines.joinToString("\n")
    }
}
