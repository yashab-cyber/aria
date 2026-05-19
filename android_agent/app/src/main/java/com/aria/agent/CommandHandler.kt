package com.aria.agent

import com.aria.agent.executors.*
import org.json.JSONObject

class CommandHandler(private val service: AriaAccessibilityService) {

    private val appExecutor = AppExecutor(service)
    private val inputExecutor = InputExecutor(service)
    private val screenExecutor = ScreenExecutor(service)
    private val fileExecutor = FileExecutor(service)
    private val whatsAppExecutor = WhatsAppExecutor(service)
    private val systemExecutor = SystemExecutor(service)
    private val mediaExecutor = MediaExecutor(service)

    suspend fun handle(command: JSONObject): JSONObject {
        val commandId = command.optString("command_id", "")
        val type = command.optString("type", "")

        return try {
            val data = when (type) {
                "tap" -> inputExecutor.tap(command.optInt("x"), command.optInt("y"))
                "tap_by_text" -> inputExecutor.tapByText(command.optString("text"))
                "tap_by_id" -> inputExecutor.tapById(command.optString("view_id"))
                "long_press" -> inputExecutor.longPress(command.optInt("x"), command.optInt("y"), command.optInt("duration_ms", 1000))
                "swipe" -> inputExecutor.swipe(command.optInt("x1"), command.optInt("y1"), command.optInt("x2"), command.optInt("y2"), command.optInt("duration_ms", 500))
                "type_text" -> inputExecutor.typeText(command.optString("text"))
                "clear_text" -> inputExecutor.clearText()
                "key_event" -> inputExecutor.keyEvent(command.optString("keycode"))
                "scroll" -> inputExecutor.scroll(command.optString("direction", "down"), command.optInt("amount", 1))
                
                "screenshot" -> screenExecutor.screenshot()
                "read_screen" -> screenExecutor.readScreen(command.optString("filter", null))
                "ui_dump" -> screenExecutor.uiDump(command.optBoolean("include_non_visible", false))
                "find_element" -> screenExecutor.findElement(command.optString("by"), command.optString("value"))
                
                "open_app" -> appExecutor.openApp(command.optString("package"))
                "close_app" -> appExecutor.closeApp(command.optString("package"))
                "list_apps" -> appExecutor.listApps(command.optBoolean("include_system", false))
                "get_current_app" -> appExecutor.getCurrentApp()
                "open_url" -> appExecutor.openUrl(command.optString("url"))
                
                "send_whatsapp" -> whatsAppExecutor.sendMessage(command.optString("phone"), command.optString("message"))
                "read_whatsapp" -> whatsAppExecutor.readMessages(if (command.has("phone")) command.getString("phone") else null, command.optInt("count", 10))
                "whatsapp_send_file" -> whatsAppExecutor.sendFile(command.optString("phone"), command.optString("file_path"))
                
                "read_file" -> fileExecutor.readFile(command.optString("path"))
                "write_file" -> fileExecutor.writeFile(command.optString("path"), command.optString("content_b64"))
                "list_files" -> fileExecutor.listFiles(command.optString("path"), command.optBoolean("recursive", false))
                "delete_file" -> fileExecutor.deleteFile(command.optString("path"))
                
                "get_battery" -> systemExecutor.getBattery()
                "get_wifi" -> systemExecutor.getWifi()
                "get_clipboard" -> systemExecutor.getClipboard()
                "set_clipboard" -> systemExecutor.setClipboard(command.optString("text"))
                "send_notification" -> systemExecutor.sendNotification(command.optString("title"), command.optString("message"))
                "set_volume" -> systemExecutor.setVolume(command.optString("stream", "music"), command.optInt("level"))
                "send_sms" -> systemExecutor.sendSms(command.optString("number"), command.optString("message"))
                "make_call" -> systemExecutor.makeCall(command.optString("number"))
                
                "media_play_pause" -> mediaExecutor.playPause()
                "media_next" -> mediaExecutor.next()
                "media_previous" -> mediaExecutor.previous()
                "set_brightness" -> mediaExecutor.setBrightness(command.optInt("level"))
                
                else -> JSONObject().apply { put("error", "Unknown command type: $type") }
            }

            JSONObject().apply {
                put("type", "result")
                put("command_id", commandId)
                put("status", if (data.has("error")) "error" else "ok")
                if (data.has("error")) put("error", data.getString("error")) else put("data", data)
            }
        } catch (e: Exception) {
            JSONObject().apply {
                put("type", "result")
                put("command_id", commandId)
                put("status", "error")
                put("error", e.message ?: "Unknown error")
            }
        }
    }
}
