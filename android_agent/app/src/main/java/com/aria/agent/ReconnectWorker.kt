package com.aria.agent

import android.accessibilityservice.AccessibilityService
import android.content.Context
import android.content.Intent
import android.util.Log
import android.view.accessibility.AccessibilityManager
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters

class ReconnectWorker(
    context: Context,
    params: WorkerParameters
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        return try {
            val manager = applicationContext.getSystemService(Context.ACCESSIBILITY_SERVICE) as AccessibilityManager
            val isEnabled = manager.isEnabled
            
            if (isEnabled) {
                val intent = Intent("com.aria.agent.RECONNECT")
                applicationContext.sendBroadcast(intent)
                Log.i("ARIA", "ReconnectWorker: reconnect broadcast sent")
            }
            Result.success()
        } catch (e: Exception) {
            Log.e("ARIA", "ReconnectWorker error", e)
            Result.retry()
        }
    }
}
