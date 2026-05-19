package com.aria.agent.executors

import android.graphics.Bitmap
import android.graphics.Rect
import android.os.Build
import android.util.Base64
import android.view.Display
import android.view.PixelCopy
import android.view.WindowManager
import android.view.accessibility.AccessibilityNodeInfo
import com.aria.agent.AriaAccessibilityService
import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.File
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

class ScreenExecutor(private val service: AriaAccessibilityService) {

    fun screenshot(): JSONObject {
        return try {
            val b64 = takeScreenshotFallback()
            JSONObject().apply {
                put("image_b64", b64)
                put("format", "png")
            }
        } catch (e: Exception) {
            JSONObject().apply { put("error", "Failed to take screenshot: ${e.message}") }
        }
    }

    private fun takeScreenshotFallback(): String {
        val file = File("/sdcard/.aria_screen.png")
        val p = Runtime.getRuntime().exec("screencap -p ${file.absolutePath}")
        p.waitFor()
        
        if (!file.exists()) throw Exception("Screencap failed to create file")
        val bytes = file.readBytes()
        file.delete()
        return Base64.encodeToString(bytes, Base64.NO_WRAP)
    }

    fun readScreen(filter: String?): JSONObject {
        val root = service.rootInActiveWindow ?: return JSONObject().apply { put("error", "Window not accessible") }
        val texts = mutableListOf<JSONObject>()
        
        fun traverse(node: AccessibilityNodeInfo) {
            val text = node.text?.toString() ?: node.contentDescription?.toString()
            if (!text.isNullOrBlank()) {
                if (filter == null || text.contains(filter, ignoreCase = true)) {
                    val rect = Rect()
                    node.getBoundsInScreen(rect)
                    texts.add(JSONObject().apply {
                        put("text", text)
                        put("bounds", rect.toShortString())
                        put("clickable", node.isClickable)
                        put("class", node.className)
                    })
                }
            }
            for (i in 0 until node.childCount) {
                node.getChild(i)?.let { traverse(it) }
            }
        }
        
        traverse(root)
        
        return JSONObject().apply {
            put("texts", JSONArray(texts))
            put("count", texts.size)
        }
    }

    fun uiDump(includeNonVisible: Boolean): JSONObject {
        val root = service.rootInActiveWindow ?: return JSONObject().apply { put("error", "Window not accessible") }
        val tree = JSONArray()
        var totalNodes = 0
        
        fun traverse(node: AccessibilityNodeInfo, depth: Int): JSONObject {
            totalNodes++
            val rect = Rect()
            node.getBoundsInScreen(rect)
            
            val obj = JSONObject().apply {
                put("class", node.className)
                put("text", node.text)
                put("desc", node.contentDescription)
                put("id", node.viewIdResourceName)
                put("bounds", rect.toShortString())
                put("clickable", node.isClickable)
                put("scrollable", node.isScrollable)
                put("editable", node.isEditable)
                put("enabled", node.isEnabled)
                put("focusable", node.isFocusable)
                put("depth", depth)
                put("child_count", node.childCount)
            }
            
            if (node.childCount > 0) {
                val children = JSONArray()
                for (i in 0 until node.childCount) {
                    node.getChild(i)?.let { 
                        if (includeNonVisible || it.isVisibleToUser) {
                            children.put(traverse(it, depth + 1))
                        }
                    }
                }
                obj.put("children", children)
            }
            return obj
        }
        
        tree.put(traverse(root, 0))
        
        return JSONObject().apply {
            put("tree", tree)
            put("total_nodes", totalNodes)
        }
    }

    fun findElement(by: String, value: String): JSONObject {
        val root = service.rootInActiveWindow ?: return JSONObject().apply { put("found", false) }
        
        val node = when (by) {
            "text" -> root.findAccessibilityNodeInfosByText(value).firstOrNull()
            "id" -> root.findAccessibilityNodeInfosByViewId(value).firstOrNull()
            "desc" -> findNodeByContentDesc(root, value)
            "class" -> findNodeByClass(root, value)
            else -> null
        }
        
        if (node != null) {
            val rect = Rect()
            node.getBoundsInScreen(rect)
            return JSONObject().apply {
                put("found", true)
                put("x", rect.centerX())
                put("y", rect.centerY())
                put("width", rect.width())
                put("height", rect.height())
                put("text", node.text)
            }
        }
        return JSONObject().apply { put("found", false) }
    }

    private fun findNodeByContentDesc(root: AccessibilityNodeInfo, desc: String): AccessibilityNodeInfo? {
        if (root.contentDescription?.toString()?.contains(desc, true) == true) return root
        for (i in 0 until root.childCount) {
            val child = root.getChild(i) ?: continue
            val result = findNodeByContentDesc(child, desc)
            if (result != null) return result
        }
        return null
    }
    
    private fun findNodeByClass(root: AccessibilityNodeInfo, className: String): AccessibilityNodeInfo? {
        if (root.className?.toString() == className) return root
        for (i in 0 until root.childCount) {
            val child = root.getChild(i) ?: continue
            val result = findNodeByClass(child, className)
            if (result != null) return result
        }
        return null
    }
}
