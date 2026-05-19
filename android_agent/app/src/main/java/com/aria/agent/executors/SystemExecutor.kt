package com.aria.agent.executors

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.media.AudioManager
import android.net.Uri
import android.net.wifi.WifiManager
import android.os.BatteryManager
import android.os.Build
import android.provider.Settings
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import com.aria.agent.AriaAccessibilityService
import com.aria.agent.NotificationHelper
import org.json.JSONObject

class SystemExecutor(private val service: AriaAccessibilityService) {

    fun getBattery(): JSONObject {
        val filter = android.content.IntentFilter(Intent.ACTION_BATTERY_CHANGED)
        val batteryStatus = service.registerReceiver(null, filter)
        
        val level = batteryStatus?.getIntExtra(BatteryManager.EXTRA_LEVEL, -1) ?: -1
        val status = batteryStatus?.getIntExtra(BatteryManager.EXTRA_STATUS, -1) ?: -1
        val isCharging = status == BatteryManager.BATTERY_STATUS_CHARGING || status == BatteryManager.BATTERY_STATUS_FULL
        val chargePlug = batteryStatus?.getIntExtra(BatteryManager.EXTRA_PLUGGED, -1) ?: -1
        
        val plugged = when (chargePlug) {
            BatteryManager.BATTERY_PLUGGED_USB -> "usb"
            BatteryManager.BATTERY_PLUGGED_AC -> "ac"
            BatteryManager.BATTERY_PLUGGED_WIRELESS -> "wireless"
            else -> "none"
        }
        
        val tempC = (batteryStatus?.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, 0) ?: 0) / 10.0f
        val voltage = batteryStatus?.getIntExtra(BatteryManager.EXTRA_VOLTAGE, 0) ?: 0
        
        return JSONObject().apply {
            put("level", level)
            put("charging", isCharging)
            put("plugged", plugged)
            put("temperature_c", tempC)
            put("voltage_mv", voltage)
        }
    }

    fun getWifi(): JSONObject {
        val wifiManager = service.applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
        val info = wifiManager.connectionInfo
        
        return JSONObject().apply {
            put("ssid", info.ssid?.removePrefix("\"")?.removeSuffix("\""))
            put("bssid", info.bssid)
            put("ip", formatIp(info.ipAddress))
            put("signal_strength", info.rssi)
            put("connected", info.networkId != -1)
            put("link_speed_mbps", info.linkSpeed)
        }
    }

    private fun formatIp(ip: Int): String {
        return "${ip and 0xFF}.${ip shr 8 and 0xFF}.${ip shr 16 and 0xFF}.${ip shr 24 and 0xFF}"
    }

    fun getClipboard(): JSONObject {
        val clipboard = service.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        val text = clipboard.primaryClip?.getItemAt(0)?.text?.toString() ?: ""
        return JSONObject().apply { put("text", text) }
    }

    fun setClipboard(text: String): JSONObject {
        val clipboard = service.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        clipboard.setPrimaryClip(ClipData.newPlainText("aria", text))
        return JSONObject().apply { put("status", "ok") }
    }

    fun sendNotification(title: String, message: String): JSONObject {
        val notification = NotificationCompat.Builder(service, NotificationHelper.CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle(title)
            .setContentText(message)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .build()
            
        // Might need POST_NOTIFICATIONS on API 33+ but service already requests it via SettingsActivity
        try {
            NotificationManagerCompat.from(service).notify(System.currentTimeMillis().toInt(), notification)
        } catch (e: SecurityException) {
            return JSONObject().apply { put("error", "Missing POST_NOTIFICATIONS permission") }
        }
        return JSONObject().apply { put("status", "ok") }
    }

    fun setVolume(streamStr: String, level: Int): JSONObject {
        val audioManager = service.getSystemService(Context.AUDIO_SERVICE) as AudioManager
        val stream = when (streamStr.lowercase()) {
            "music" -> AudioManager.STREAM_MUSIC
            "ring" -> AudioManager.STREAM_RING
            "alarm" -> AudioManager.STREAM_ALARM
            "voice_call" -> AudioManager.STREAM_VOICE_CALL
            "notification" -> AudioManager.STREAM_NOTIFICATION
            else -> AudioManager.STREAM_MUSIC
        }
        
        val max = audioManager.getStreamMaxVolume(stream)
        val target = ((level / 100.0) * max).toInt().coerceIn(0, max)
        
        try {
            audioManager.setStreamVolume(stream, target, AudioManager.FLAG_SHOW_UI)
        } catch (e: Exception) {
            return JSONObject().apply { put("error", "Do Not Disturb might be active") }
        }
        return JSONObject().apply {
            put("status", "ok")
            put("stream", streamStr)
            put("level", level)
        }
    }

    fun sendSms(number: String, message: String): JSONObject {
        val intent = Intent(Intent.ACTION_SENDTO, Uri.parse("sms:$number")).apply {
            putExtra("sms_body", message)
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        service.startActivity(intent)
        return JSONObject().apply { put("status", "ok") }
    }

    fun makeCall(number: String): JSONObject {
        val intent = Intent(Intent.ACTION_CALL, Uri.parse("tel:$number")).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        try {
            service.startActivity(intent)
        } catch (e: SecurityException) {
            return JSONObject().apply { put("error", "Missing CALL_PHONE permission") }
        }
        return JSONObject().apply { put("status", "ok") }
    }
}
