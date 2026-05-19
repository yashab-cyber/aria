package com.aria.agent

import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

class SettingsActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        // Simple programmatic UI for settings to avoid complex XML layouts
        val layout = android.widget.LinearLayout(this).apply {
            orientation = android.widget.LinearLayout.VERTICAL
            setPadding(32, 32, 32, 32)
        }
        
        val title = TextView(this).apply {
            text = "ARIA Agent Settings"
            textSize = 24f
            setPadding(0, 0, 0, 32)
        }
        layout.addView(title)
        
        val masterKey = MasterKey.Builder(this)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()
            
        val prefs = EncryptedSharedPreferences.create(
            this,
            "aria_prefs",
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
        )
        
        val urlInput = EditText(this).apply {
            hint = "Server URL (e.g. ws://192.168.1.100:8000/ws/device)"
            setText(prefs.getString("server_url", "ws://192.168.1.100:8000/ws/device"))
        }
        layout.addView(urlInput)
        
        val nameInput = EditText(this).apply {
            hint = "Device Name"
            setText(prefs.getString("device_name", Build.MODEL))
        }
        layout.addView(nameInput)
        
        val saveBtn = Button(this).apply {
            text = "Save Configuration"
            setOnClickListener {
                prefs.edit()
                    .putString("server_url", urlInput.text.toString())
                    .putString("device_name", nameInput.text.toString())
                    .apply()
                Toast.makeText(this@SettingsActivity, "Saved", Toast.LENGTH_SHORT).show()
                
                AriaAccessibilityService.instance?.webSocketClient?.disconnect()
                AriaAccessibilityService.instance?.webSocketClient?.connect()
            }
        }
        layout.addView(saveBtn)
        
        val accessBtn = Button(this).apply {
            text = "Open Accessibility Settings"
            setOnClickListener {
                startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
            }
        }
        layout.addView(accessBtn)
        
        val statusText = TextView(this).apply {
            text = "Status: Check Accessibility Settings"
            setPadding(0, 32, 0, 0)
        }
        layout.addView(statusText)
        
        setContentView(layout)
        
        ReconnectWorker.schedule(this)
    }
}
