package com.aria.agent.executors

import android.accessibilityservice.AccessibilityService
import android.content.Intent
import android.content.pm.ApplicationInfo
import android.content.pm.PackageManager
import android.net.Uri
import com.aria.agent.AriaAccessibilityService
import org.json.JSONArray
import org.json.JSONObject

class AppExecutor(private val service: AriaAccessibilityService) {

    fun openApp(packageName: String): JSONObject {
        val intent = service.packageManager.getLaunchIntentForPackage(packageName)
        if (intent != null) {
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            service.startActivity(intent)
            return JSONObject().apply {
                put("status", "ok")
                put("package", packageName)
            }
        }
        return JSONObject().apply {
            put("status", "not_found")
            put("package", packageName)
        }
    }

    fun closeApp(packageName: String): JSONObject {
        service.performGlobalAction(AccessibilityService.GLOBAL_ACTION_HOME)
        return JSONObject().apply {
            put("status", "ok")
        }
    }

    fun listApps(includeSystem: Boolean): JSONObject {
        val pm = service.packageManager
        val packages = pm.getInstalledApplications(PackageManager.GET_META_DATA)
        val jsonArray = JSONArray()

        for (appInfo in packages) {
            val isSystem = (appInfo.flags and ApplicationInfo.FLAG_SYSTEM) != 0
            if (!includeSystem && isSystem) continue

            val name = pm.getApplicationLabel(appInfo).toString()
            val version = try {
                pm.getPackageInfo(appInfo.packageName, 0).versionName
            } catch (e: Exception) {
                "unknown"
            }

            jsonArray.put(JSONObject().apply {
                put("name", name)
                put("package", appInfo.packageName)
                put("version", version)
                put("system", isSystem)
            })
        }

        return JSONObject().apply {
            put("apps", jsonArray)
            put("count", jsonArray.length())
        }
    }

    fun getCurrentApp(): JSONObject {
        return JSONObject().apply {
            put("package", service.currentPackage)
            put("activity", service.currentActivity)
        }
    }

    fun openUrl(url: String): JSONObject {
        val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url)).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        service.startActivity(intent)
        return JSONObject().apply {
            put("status", "ok")
            put("url", url)
        }
    }
}
