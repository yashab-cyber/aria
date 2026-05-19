package com.aria.agent.executors

import android.content.Intent
import android.net.Uri
import com.aria.agent.AriaAccessibilityService

class AppExecutor(private val service: AriaAccessibilityService) {

    fun openApp(params: Map<String, Any>): Map<String, Any?> {
        val packageName = params["package"] as? String ?: return mapOf("status" to "error", "message" to "package required")
        val pm = service.packageManager
        val intent = pm.getLaunchIntentForPackage(packageName)
        if (intent != null) {
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            service.startActivity(intent)
            return mapOf("status" to "ok")
        }
        return mapOf("status" to "not_found")
    }

    fun closeApp(params: Map<String, Any>): Map<String, Any?> {
        // Accessibility service cannot arbitrarily kill background apps easily, 
        // but we can send user to HOME to background the current app.
        service.performGlobalAction(AriaAccessibilityService.GLOBAL_ACTION_HOME)
        return mapOf("status" to "ok")
    }

    fun listApps(params: Map<String, Any>): Map<String, Any?> {
        val includeSystem = params["include_system"] as? Boolean ?: false
        val pm = service.packageManager
        val apps = pm.getInstalledApplications(0).mapNotNull { info ->
            val isSystem = (info.flags and android.content.pm.ApplicationInfo.FLAG_SYSTEM) != 0
            if (!includeSystem && isSystem) null
            else mapOf(
                "name" to pm.getApplicationLabel(info).toString(),
                "package" to info.packageName,
                "system" to isSystem
            )
        }
        return mapOf("apps" to apps)
    }

    fun getCurrentApp(): Map<String, Any?> {
        return mapOf(
            "package" to service.currentActivePackage,
            "activity" to service.currentActiveActivity
        )
    }

    fun openUrl(params: Map<String, Any>): Map<String, Any?> {
        val url = params["url"] as? String ?: return mapOf("status" to "error", "message" to "url required")
        val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url)).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        service.startActivity(intent)
        return mapOf("status" to "ok")
    }
}
