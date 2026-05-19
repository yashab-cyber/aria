package com.aria.agent.executors

import android.graphics.Rect
import android.util.Base64
import android.view.accessibility.AccessibilityNodeInfo
import com.aria.agent.AriaAccessibilityService
import java.io.File

class ScreenExecutor(private val service: AriaAccessibilityService) {

    fun screenshot(): Map<String, Any?> {
        try {
            // Using screencap via shell as fallback since MediaProjection requires Activity result
            val tempFile = File("/sdcard/.aria_tmp.png")
            val process = Runtime.getRuntime().exec("screencap -p ${tempFile.absolutePath}")
            process.waitFor()
            
            if (tempFile.exists()) {
                val bytes = tempFile.readBytes()
                val b64 = Base64.encodeToString(bytes, Base64.NO_WRAP)
                tempFile.delete()
                return mapOf("image_b64" to b64, "format" to "png")
            }
        } catch (e: Exception) {
            return mapOf("status" to "error", "message" to e.message)
        }
        return mapOf("status" to "error", "message" to "screencap failed")
    }

    fun readScreen(params: Map<String, Any>): Map<String, Any?> {
        val filter = params["filter"] as? String
        val root = service.rootInActiveWindow ?: return mapOf("texts" to emptyList<Any>())
        
        val results = mutableListOf<Map<String, Any>>()
        traverseForText(root, filter?.lowercase(), results)
        
        return mapOf("texts" to results)
    }

    private fun traverseForText(node: AccessibilityNodeInfo, filter: String?, results: MutableList<Map<String, Any>>) {
        val text = node.text?.toString() ?: node.contentDescription?.toString()
        
        if (!text.isNullOrBlank()) {
            if (filter == null || text.lowercase().contains(filter)) {
                val bounds = Rect()
                node.getBoundsInScreen(bounds)
                results.add(mapOf(
                    "text" to text,
                    "bounds" to "${bounds.left},${bounds.top},${bounds.right},${bounds.bottom}",
                    "clickable" to node.isClickable
                ))
            }
        }
        
        for (i in 0 until node.childCount) {
            val child = node.getChild(i) ?: continue
            traverseForText(child, filter, results)
        }
    }

    fun uiDump(params: Map<String, Any>): Map<String, Any?> {
        val includeNonVisible = params["include_non_visible"] as? Boolean ?: false
        val root = service.rootInActiveWindow ?: return mapOf("nodes" to emptyList<Any>())
        
        val results = mutableListOf<Map<String, Any>>()
        traverseForDump(root, 0, includeNonVisible, results)
        
        return mapOf("nodes" to results)
    }

    private fun traverseForDump(node: AccessibilityNodeInfo, depth: Int, includeNonVisible: Boolean, results: MutableList<Map<String, Any>>) {
        if (!includeNonVisible && !node.isVisibleToUser) return
        
        val bounds = Rect()
        node.getBoundsInScreen(bounds)
        
        results.add(mapOf(
            "class" to (node.className?.toString() ?: ""),
            "text" to (node.text?.toString() ?: ""),
            "desc" to (node.contentDescription?.toString() ?: ""),
            "id" to (node.viewIdResourceName ?: ""),
            "bounds" to "${bounds.left},${bounds.top},${bounds.right},${bounds.bottom}",
            "clickable" to node.isClickable,
            "scrollable" to node.isScrollable,
            "editable" to node.isEditable,
            "depth" to depth
        ))
        
        for (i in 0 until node.childCount) {
            val child = node.getChild(i) ?: continue
            traverseForDump(child, depth + 1, includeNonVisible, results)
        }
    }

    fun findElement(params: Map<String, Any>): Map<String, Any?> {
        val by = params["by"] as? String ?: return mapOf("found" to false)
        val value = params["value"] as? String ?: return mapOf("found" to false)
        val root = service.rootInActiveWindow ?: return mapOf("found" to false)
        
        val node = when (by) {
            "id" -> root.findAccessibilityNodeInfosByViewId(value).firstOrNull()
            "text", "desc", "class" -> findNodeGeneric(root, by, value.lowercase())
            else -> null
        }
        
        if (node != null) {
            val bounds = Rect()
            node.getBoundsInScreen(bounds)
            return mapOf(
                "found" to true,
                "x" to bounds.centerX(),
                "y" to bounds.centerY(),
                "width" to bounds.width(),
                "height" to bounds.height(),
                "text" to (node.text ?: node.contentDescription ?: "").toString(),
                "id" to (node.viewIdResourceName ?: "")
            )
        }
        return mapOf("found" to false)
    }
    
    private fun findNodeGeneric(root: AccessibilityNodeInfo, by: String, value: String): AccessibilityNodeInfo? {
        val matches = when (by) {
            "text" -> root.text?.toString()?.lowercase()?.contains(value) == true
            "desc" -> root.contentDescription?.toString()?.lowercase()?.contains(value) == true
            "class" -> root.className?.toString()?.lowercase()?.contains(value) == true
            else -> false
        }
        if (matches) return root
        
        for (i in 0 until root.childCount) {
            val child = root.getChild(i) ?: continue
            val found = findNodeGeneric(child, by, value)
            if (found != null) return found
        }
        return null
    }
}
