package com.aria.agent.executors

import android.accessibilityservice.GestureDescription
import android.graphics.Path
import android.os.Bundle
import android.view.accessibility.AccessibilityNodeInfo
import com.aria.agent.AriaAccessibilityService
import kotlinx.coroutines.delay

class InputExecutor(private val service: AriaAccessibilityService) {

    fun tap(params: Map<String, Any>): Map<String, Any?> {
        val x = (params["x"] as? Number)?.toFloat() ?: return mapOf("status" to "error")
        val y = (params["y"] as? Number)?.toFloat() ?: return mapOf("status" to "error")
        
        val path = Path().apply { moveTo(x, y) }
        val stroke = GestureDescription.StrokeDescription(path, 0, 100)
        val gesture = GestureDescription.Builder().addStroke(stroke).build()
        
        val success = service.dispatchGesture(gesture, null, null)
        return mapOf("status" to if (success) "ok" else "error")
    }

    fun longPress(params: Map<String, Any>): Map<String, Any?> {
        val x = (params["x"] as? Number)?.toFloat() ?: return mapOf("status" to "error")
        val y = (params["y"] as? Number)?.toFloat() ?: return mapOf("status" to "error")
        val duration = (params["duration_ms"] as? Number)?.toLong() ?: 1000L
        
        val path = Path().apply { moveTo(x, y) }
        val stroke = GestureDescription.StrokeDescription(path, 0, duration)
        val gesture = GestureDescription.Builder().addStroke(stroke).build()
        
        val success = service.dispatchGesture(gesture, null, null)
        return mapOf("status" to if (success) "ok" else "error")
    }

    fun swipe(params: Map<String, Any>): Map<String, Any?> {
        val x1 = (params["x1"] as? Number)?.toFloat() ?: return mapOf("status" to "error")
        val y1 = (params["y1"] as? Number)?.toFloat() ?: return mapOf("status" to "error")
        val x2 = (params["x2"] as? Number)?.toFloat() ?: return mapOf("status" to "error")
        val y2 = (params["y2"] as? Number)?.toFloat() ?: return mapOf("status" to "error")
        val duration = (params["duration_ms"] as? Number)?.toLong() ?: 500L
        
        val path = Path().apply { 
            moveTo(x1, y1)
            lineTo(x2, y2)
        }
        val stroke = GestureDescription.StrokeDescription(path, 0, duration)
        val gesture = GestureDescription.Builder().addStroke(stroke).build()
        
        val success = service.dispatchGesture(gesture, null, null)
        return mapOf("status" to if (success) "ok" else "error")
    }
    
    fun tapByText(params: Map<String, Any>): Map<String, Any?> {
        val text = params["text"] as? String ?: return mapOf("found" to false)
        val root = service.rootInActiveWindow ?: return mapOf("found" to false, "message" to "No active window")
        
        val node = findNodeByText(root, text.lowercase())
        if (node != null) {
            val success = node.performAction(AccessibilityNodeInfo.ACTION_CLICK)
            return mapOf("found" to true, "clicked" to success, "node_text" to (node.text ?: node.contentDescription ?: "").toString())
        }
        return mapOf("found" to false)
    }
    
    fun tapById(params: Map<String, Any>): Map<String, Any?> {
        val viewId = params["view_id"] as? String ?: return mapOf("found" to false)
        val root = service.rootInActiveWindow ?: return mapOf("found" to false, "message" to "No active window")
        
        val nodes = root.findAccessibilityNodeInfosByViewId(viewId)
        if (nodes.isNotEmpty()) {
            val node = nodes[0]
            val success = node.performAction(AccessibilityNodeInfo.ACTION_CLICK)
            return mapOf("found" to true, "clicked" to success)
        }
        return mapOf("found" to false)
    }

    suspend fun typeText(params: Map<String, Any>): Map<String, Any?> {
        val text = params["text"] as? String ?: return mapOf("status" to "error")
        val root = service.rootInActiveWindow ?: return mapOf("status" to "error", "message" to "No window")
        
        val focused = root.findFocus(AccessibilityNodeInfo.FOCUS_INPUT)
        if (focused != null && focused.isEditable) {
            val args = Bundle().apply { putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text) }
            focused.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)
            return mapOf("status" to "ok")
        }
        
        // Find first editable node if none focused
        val node = findFirstEditable(root)
        if (node != null) {
            val args = Bundle().apply { putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text) }
            node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)
            return mapOf("status" to "ok")
        }
        return mapOf("status" to "error", "message" to "No editable field found")
    }
    
    fun clearText(): Map<String, Any?> {
        val root = service.rootInActiveWindow ?: return mapOf("status" to "error")
        val focused = root.findFocus(AccessibilityNodeInfo.FOCUS_INPUT) ?: findFirstEditable(root)
        
        if (focused != null) {
            val args = Bundle().apply { putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, "") }
            focused.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)
            return mapOf("status" to "ok")
        }
        return mapOf("status" to "error")
    }

    fun keyEvent(params: Map<String, Any>): Map<String, Any?> {
        val keycodeStr = params["keycode"] as? String ?: return mapOf("status" to "error")
        
        val action = when (keycodeStr.uppercase()) {
            "BACK" -> AriaAccessibilityService.GLOBAL_ACTION_BACK
            "HOME" -> AriaAccessibilityService.GLOBAL_ACTION_HOME
            "RECENT_APPS" -> AriaAccessibilityService.GLOBAL_ACTION_RECENTS
            "POWER" -> AriaAccessibilityService.GLOBAL_ACTION_POWER_DIALOG
            "NOTIFICATIONS" -> AriaAccessibilityService.GLOBAL_ACTION_NOTIFICATIONS
            else -> null
        }
        
        if (action != null) {
            service.performGlobalAction(action)
            return mapOf("status" to "ok")
        }
        return mapOf("status" to "unsupported", "message" to "Only global actions supported easily in Accessibility")
    }

    fun scroll(params: Map<String, Any>): Map<String, Any?> {
        val dir = params["direction"] as? String ?: "down"
        val root = service.rootInActiveWindow ?: return mapOf("status" to "error")
        val scrollable = findFirstScrollable(root) ?: return mapOf("status" to "error", "message" to "No scrollable node")
        
        val action = if (dir == "up" || dir == "left") AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD else AccessibilityNodeInfo.ACTION_SCROLL_FORWARD
        scrollable.performAction(action)
        return mapOf("status" to "ok")
    }
    
    // --- Helpers ---
    
    private fun findNodeByText(root: AccessibilityNodeInfo, text: String): AccessibilityNodeInfo? {
        val content = root.text?.toString()?.lowercase() ?: ""
        val desc = root.contentDescription?.toString()?.lowercase() ?: ""
        
        if ((content.contains(text) || desc.contains(text)) && root.isClickable) {
            return root
        }
        
        for (i in 0 until root.childCount) {
            val child = root.getChild(i) ?: continue
            val found = findNodeByText(child, text)
            if (found != null) return found
        }
        return null
    }
    
    private fun findFirstEditable(root: AccessibilityNodeInfo): AccessibilityNodeInfo? {
        if (root.isEditable) return root
        for (i in 0 until root.childCount) {
            val child = root.getChild(i) ?: continue
            val found = findFirstEditable(child)
            if (found != null) return found
        }
        return null
    }
    
    private fun findFirstScrollable(root: AccessibilityNodeInfo): AccessibilityNodeInfo? {
        if (root.isScrollable) return root
        for (i in 0 until root.childCount) {
            val child = root.getChild(i) ?: continue
            val found = findFirstScrollable(child)
            if (found != null) return found
        }
        return null
    }
}
