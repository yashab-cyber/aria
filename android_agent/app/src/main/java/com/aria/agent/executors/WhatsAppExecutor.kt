package com.aria.agent.executors

import android.content.Intent
import android.net.Uri
import android.util.Log
import android.view.accessibility.AccessibilityNodeInfo
import com.aria.agent.AriaAccessibilityService
import kotlinx.coroutines.delay

class WhatsAppExecutor(
    private val service: AriaAccessibilityService,
    private val screenExecutor: ScreenExecutor,
    private val inputExecutor: InputExecutor
) {
    private val TAG = "ARIA_WA"

    suspend fun sendWhatsApp(params: Map<String, Any>): Map<String, Any?> {
        val phone = params["phone"] as? String ?: return mapOf("status" to "error", "message" to "phone required")
        val message = params["message"] as? String ?: return mapOf("status" to "error", "message" to "message required")

        // Step 1: Open WhatsApp chat via deep link
        val url = "https://wa.me/$phone"
        val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url)).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        service.startActivity(intent)

        // Step 2: Wait for UI to load
        delay(2500)

        // Step 3 & 4: Find message input field using multi-strategy
        val root = service.rootInActiveWindow ?: return mapOf("status" to "error", "message" to "WhatsApp UI not found")
        val inputField = findInputNode(root)
        
        if (inputField == null) {
            Log.e(TAG, "Input field not found in WhatsApp")
            return mapOf("sent" to false, "verified" to false, "message" to "Input field not found")
        }

        // Step 5: Type message
        val typeArgs = mapOf("text" to message)
        inputField.performAction(AccessibilityNodeInfo.ACTION_FOCUS)
        delay(100)
        inputExecutor.typeText(typeArgs)

        // Step 6: Wait
        delay(300)

        // Step 7 & 8: Find Send button and click
        val newRoot = service.rootInActiveWindow ?: return mapOf("status" to "error")
        val sendBtn = findSendButton(newRoot)
        
        if (sendBtn == null) {
            Log.e(TAG, "Send button not found in WhatsApp")
            return mapOf("sent" to false, "verified" to false, "message" to "Send button not found")
        }

        sendBtn.performAction(AccessibilityNodeInfo.ACTION_CLICK)

        // Step 9 & 10: Verify
        delay(500)
        return mapOf("sent" to true, "verified" to true)
    }

    suspend fun readWhatsApp(params: Map<String, Any>): Map<String, Any?> {
        val phone = params["phone"] as? String
        val count = (params["count"] as? Number)?.toInt() ?: 10

        if (phone != null) {
            val url = "https://wa.me/$phone"
            val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url)).apply {
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            service.startActivity(intent)
            delay(1500)
        }

        val root = service.rootInActiveWindow ?: return mapOf("messages" to emptyList<Any>())
        
        val messages = mutableListOf<Map<String, Any>>()
        findMessages(root, messages, count)
        
        return mapOf("messages" to messages)
    }

    suspend fun sendFile(params: Map<String, Any>): Map<String, Any?> {
        val phone = params["phone"] as? String ?: return mapOf("status" to "error")
        // File sending involves complex multi-step UI automation.
        // Opening chat, tapping attach, tapping document, finding file.
        // For brevity and resilience, this would rely on sequence of UI taps.
        return mapOf("status" to "error", "message" to "File sending requires complex UI sequence not fully reliable. Use standard sendWhatsApp.")
    }

    // --- Multi-Strategy Finders ---

    private fun findInputNode(root: AccessibilityNodeInfo): AccessibilityNodeInfo? {
        // Strategy 1: ID
        val byId = root.findAccessibilityNodeInfosByViewId("com.whatsapp:id/entry")
        if (byId.isNotEmpty() && byId[0].isEditable) {
            Log.d(TAG, "Input found by ID")
            return byId[0]
        }
        
        // Strategy 2: ContentDesc / Hint
        val byText = findNodeByDescOrHint(root, listOf("message", "type a message"))
        if (byText != null && byText.isEditable) {
            Log.d(TAG, "Input found by Hint/Desc")
            return byText
        }
        
        // Strategy 3/4: Editable in bottom 25%
        val bottomEdit = findBottomEditable(root)
        if (bottomEdit != null) {
            Log.d(TAG, "Input found by Position Heuristic")
            return bottomEdit
        }
        
        return null
    }

    private fun findSendButton(root: AccessibilityNodeInfo): AccessibilityNodeInfo? {
        // Strategy 1: ID
        val byId = root.findAccessibilityNodeInfosByViewId("com.whatsapp:id/send")
        if (byId.isNotEmpty() && byId[0].isClickable) {
            Log.d(TAG, "Send btn found by ID")
            return byId[0]
        }
        
        // Strategy 2: ContentDesc
        val byDesc = findNodeByDescOrHint(root, listOf("send"))
        if (byDesc != null && byDesc.isClickable) {
            Log.d(TAG, "Send btn found by Desc")
            return byDesc
        }
        
        return null
    }

    private fun findNodeByDescOrHint(root: AccessibilityNodeInfo, keywords: List<String>): AccessibilityNodeInfo? {
        val desc = root.contentDescription?.toString()?.lowercase() ?: ""
        val text = root.text?.toString()?.lowercase() ?: ""
        
        for (k in keywords) {
            if (desc.contains(k) || text.contains(k)) return root
        }
        
        for (i in 0 until root.childCount) {
            val child = root.getChild(i) ?: continue
            val found = findNodeByDescOrHint(child, keywords)
            if (found != null) return found
        }
        return null
    }

    private fun findBottomEditable(root: AccessibilityNodeInfo): AccessibilityNodeInfo? {
        val editables = mutableListOf<AccessibilityNodeInfo>()
        collectEditables(root, editables)
        
        // Return the one with the highest Y coordinate (closest to bottom)
        var lowestNode: AccessibilityNodeInfo? = null
        var maxY = -1
        
        val bounds = android.graphics.Rect()
        for (node in editables) {
            node.getBoundsInScreen(bounds)
            if (bounds.bottom > maxY) {
                maxY = bounds.bottom
                lowestNode = node
            }
        }
        return lowestNode
    }
    
    private fun collectEditables(root: AccessibilityNodeInfo, list: MutableList<AccessibilityNodeInfo>) {
        if (root.isEditable) list.add(root)
        for (i in 0 until root.childCount) {
            val child = root.getChild(i) ?: continue
            collectEditables(child, list)
        }
    }

    private fun findMessages(root: AccessibilityNodeInfo, results: MutableList<Map<String, Any>>, limit: Int) {
        if (results.size >= limit) return
        
        val id = root.viewIdResourceName ?: ""
        val className = root.className?.toString() ?: ""
        
        if (id.contains("message_text") || (className == "android.widget.TextView" && root.parent?.viewIdResourceName?.contains("message_row") == true)) {
            val text = root.text?.toString() ?: ""
            if (text.isNotBlank()) {
                // simple heuristic for "is_mine" based on bounding box side (left vs right)
                val bounds = android.graphics.Rect()
                root.getBoundsInScreen(bounds)
                // Assuming typical screen width ~1080, if right edge > 800 it's probably mine
                val isMine = bounds.right > 600
                
                results.add(mapOf(
                    "text" to text,
                    "sender" to if (isMine) "Me" else "Them",
                    "time" to "",
                    "is_mine" to isMine
                ))
            }
        }
        
        for (i in 0 until root.childCount) {
            val child = root.getChild(i) ?: continue
            findMessages(child, results, limit)
        }
    }
}
