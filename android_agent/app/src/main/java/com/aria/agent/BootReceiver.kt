package com.aria.agent

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log

class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == Intent.ACTION_BOOT_COMPLETED) {
            Log.i("ARIA_BOOT", "Device booted. ARIA Accessibility Service will be started by Android if enabled.")
            // Enqueue the WorkManager worker to act as a watchdog
            ReconnectWorker.schedule(context)
        }
    }
}
