package com.aria.agent.executors

import android.app.NotificationManager
import android.content.ClipboardManager
import android.content.ClipData
import android.content.Context
import android.content.Intent
import android.media.AudioManager
import android.net.Uri
import android.net.wifi.WifiManager
import android.os.BatteryManager
import android.content.IntentFilter
import androidx.core.app.NotificationCompat
import com.aria.agent.AriaAccessibilityService

class SystemExecutor(private val service: AriaAccessibilityService) {

    fun getBattery(): Map<String, Any?> {
        val filter = IntentFilter(Intent.ACTION_BATTERY_CHANGED)
        val intent = service.registerReceiver(null, filter)
        
        val level = intent?.getIntExtra(BatteryManager.EXTRA_LEVEL, -1) ?: -1
        val status = intent?.getIntExtra(BatteryManager.EXTRA_STATUS, -1) ?: -1
        val charging = status == BatteryManager.BATTERY_STATUS_CHARGING || status == BatteryManager.BATTERY_STATUS_FULL
        val plugged = intent?.getIntExtra(BatteryManager.EXTRA_PLUGGED, -1) ?: -1
        val temp = (intent?.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, 0) ?: 0) / 10.0f
        
        val plugStr = when (plugged) {
            BatteryManager.BATTERY_PLUGGED_AC -> "AC"
            BatteryManager.BATTERY_PLUGGED_USB -> "USB"
            BatteryManager.BATTERY_PLUGGED_WIRELESS -> "WIRELESS"
            else -> "UNPLUGGED"
        }
        
        return mapOf(
            "level" to level,
            "charging" to charging,
            "plugged" to plugStr,
            "temperature" to temp
        )
    }

    fun getWifi(): Map<String, Any?> {
        val wifiManager = service.applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
        val info = wifiManager.connectionInfo
        
        val ip = info.ipAddress
        val ipString = String.format(
            "%d.%d.%d.%d",
            ip and 0xff,
            ip shr 8 and 0xff,
            ip shr 16 and 0xff,
            ip shr 24 and 0xff
        )
        
        return mapOf(
            "ssid" to info.ssid?.replace("\"", ""),
            "ip" to ipString,
            "signal_strength" to WifiManager.calculateSignalLevel(info.rssi, 100),
            "connected" to (ip != 0)
        )
    }

    fun getClipboard(): Map<String, Any?> {
        val clipboard = service.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        if (clipboard.hasPrimaryClip()) {
            val item = clipboard.primaryClip?.getItemAt(0)
            return mapOf("text" to (item?.text?.toString() ?: ""))
        }
        return mapOf("text" to "")
    }

    fun setClipboard(params: Map<String, Any>): Map<String, Any?> {
        val text = params["text"] as? String ?: return mapOf("status" to "error")
        val clipboard = service.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        val clip = ClipData.newPlainText("ARIA", text)
        clipboard.setPrimaryClip(clip)
        return mapOf("status" to "ok")
    }

    fun sendNotification(params: Map<String, Any>): Map<String, Any?> {
        val title = params["title"] as? String ?: "ARIA"
        val message = params["message"] as? String ?: return mapOf("status" to "error")
        
        val manager = service.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val builder = NotificationCompat.Builder(service, "aria_agent_service")
            .setContentTitle(title)
            .setContentText(message)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setAutoCancel(true)
            
        manager.notify(System.currentTimeMillis().toInt(), builder.build())
        return mapOf("status" to "ok")
    }

    fun setVolume(params: Map<String, Any>): Map<String, Any?> {
        val streamStr = params["stream"] as? String ?: "music"
        val levelPercent = params["level"] as? Int ?: return mapOf("status" to "error")
        
        val stream = when (streamStr) {
            "ring" -> AudioManager.STREAM_RING
            "alarm" -> AudioManager.STREAM_ALARM
            else -> AudioManager.STREAM_MUSIC
        }
        
        val audioManager = service.getSystemService(Context.AUDIO_SERVICE) as AudioManager
        val max = audioManager.getStreamMaxVolume(stream)
        val target = (max * (levelPercent / 100.0)).toInt()
        
        audioManager.setStreamVolume(stream, target, 0)
        return mapOf("status" to "ok")
    }

    fun sendSms(params: Map<String, Any>): Map<String, Any?> {
        val number = params["number"] as? String ?: return mapOf("status" to "error")
        val message = params["message"] as? String ?: return mapOf("status" to "error")
        
        val intent = Intent(Intent.ACTION_SENDTO).apply {
            data = Uri.parse("smsto:$number")
            putExtra("sms_body", message)
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        service.startActivity(intent)
        return mapOf("status" to "ok")
    }

    fun makeCall(params: Map<String, Any>): Map<String, Any?> {
        val number = params["number"] as? String ?: return mapOf("status" to "error")
        val intent = Intent(Intent.ACTION_CALL).apply {
            data = Uri.parse("tel:$number")
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        
        return try {
            service.startActivity(intent)
            mapOf("status" to "ok")
        } catch (e: SecurityException) {
            mapOf("status" to "error", "message" to "CALL_PHONE permission required")
        }
    }
}
