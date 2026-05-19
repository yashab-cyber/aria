package com.aria.agent.executors

import android.content.Context
import android.media.AudioManager
import android.provider.Settings
import android.view.KeyEvent
import com.aria.agent.AriaAccessibilityService
import org.json.JSONObject

class MediaExecutor(private val service: AriaAccessibilityService) {

    fun playPause(): JSONObject {
        dispatchMediaKey(KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE)
        return JSONObject().apply {
            put("status", "ok")
            put("action", "play_pause")
        }
    }

    fun next(): JSONObject {
        dispatchMediaKey(KeyEvent.KEYCODE_MEDIA_NEXT)
        return JSONObject().apply {
            put("status", "ok")
            put("action", "next")
        }
    }

    fun previous(): JSONObject {
        dispatchMediaKey(KeyEvent.KEYCODE_MEDIA_PREVIOUS)
        return JSONObject().apply {
            put("status", "ok")
            put("action", "previous")
        }
    }

    fun setBrightness(level: Int): JSONObject {
        return try {
            val converted = ((level / 100.0) * 255).toInt().coerceIn(0, 255)
            val resolver = service.contentResolver
            
            Settings.System.putInt(resolver, Settings.System.SCREEN_BRIGHTNESS_MODE, Settings.System.SCREEN_BRIGHTNESS_MODE_MANUAL)
            Settings.System.putInt(resolver, Settings.System.SCREEN_BRIGHTNESS, converted)
            
            JSONObject().apply {
                put("status", "ok")
                put("level", level)
            }
        } catch (e: SecurityException) {
            JSONObject().apply { put("error", "Missing WRITE_SETTINGS permission") }
        } catch (e: Exception) {
            JSONObject().apply { put("error", e.message) }
        }
    }

    private fun dispatchMediaKey(keyCode: Int) {
        val audioManager = service.getSystemService(Context.AUDIO_SERVICE) as AudioManager
        audioManager.dispatchMediaKeyEvent(KeyEvent(KeyEvent.ACTION_DOWN, keyCode))
        audioManager.dispatchMediaKeyEvent(KeyEvent(KeyEvent.ACTION_UP, keyCode))
    }
}
