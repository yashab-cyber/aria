package com.aria.agent

import com.aria.agent.executors.*

class CommandHandler(private val service: AriaAccessibilityService) {
    
    private val appExecutor = AppExecutor(service)
    private val inputExecutor = InputExecutor(service)
    private val screenExecutor = ScreenExecutor(service)
    private val fileExecutor = FileExecutor(service)
    private val systemExecutor = SystemExecutor(service)
    private val whatsappExecutor = WhatsAppExecutor(service, screenExecutor, inputExecutor)
    
    suspend fun handleCommand(type: String, params: Map<String, Any>): Map<String, Any?> {
        return when (type) {
            // Input Commands
            "tap" -> inputExecutor.tap(params)
            "tap_by_text" -> inputExecutor.tapByText(params)
            "tap_by_id" -> inputExecutor.tapById(params)
            "long_press" -> inputExecutor.longPress(params)
            "swipe" -> inputExecutor.swipe(params)
            "type_text" -> inputExecutor.typeText(params)
            "clear_text" -> inputExecutor.clearText()
            "key_event" -> inputExecutor.keyEvent(params)
            "scroll" -> inputExecutor.scroll(params)
            
            // Screen Commands
            "screenshot" -> screenExecutor.screenshot()
            "read_screen" -> screenExecutor.readScreen(params)
            "ui_dump" -> screenExecutor.uiDump(params)
            "find_element" -> screenExecutor.findElement(params)
            
            // App Commands
            "open_app" -> appExecutor.openApp(params)
            "close_app" -> appExecutor.closeApp(params)
            "list_apps" -> appExecutor.listApps(params)
            "get_current_app" -> appExecutor.getCurrentApp()
            "open_url" -> appExecutor.openUrl(params)
            
            // WhatsApp Commands
            "send_whatsapp" -> whatsappExecutor.sendWhatsApp(params)
            "read_whatsapp" -> whatsappExecutor.readWhatsApp(params)
            "whatsapp_send_file" -> whatsappExecutor.sendFile(params)
            
            // File Commands
            "read_file" -> fileExecutor.readFile(params)
            "write_file" -> fileExecutor.writeFile(params)
            "list_files" -> fileExecutor.listFiles(params)
            "delete_file" -> fileExecutor.deleteFile(params)
            
            // System Commands
            "get_battery" -> systemExecutor.getBattery()
            "get_wifi" -> systemExecutor.getWifi()
            "get_clipboard" -> systemExecutor.getClipboard()
            "set_clipboard" -> systemExecutor.setClipboard(params)
            "send_notification" -> systemExecutor.sendNotification(params)
            "set_volume" -> systemExecutor.setVolume(params)
            "send_sms" -> systemExecutor.sendSms(params)
            "make_call" -> systemExecutor.makeCall(params)
            
            else -> throw IllegalArgumentException("Unknown command type: $type")
        }
    }
}
