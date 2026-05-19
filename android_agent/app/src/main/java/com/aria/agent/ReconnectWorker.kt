package com.aria.agent

import android.content.Context
import androidx.work.*
import java.util.concurrent.TimeUnit

class ReconnectWorker(context: Context, params: WorkerParameters) : Worker(context, params) {
    override fun doWork(): Result {
        val service = AriaAccessibilityService.instance
        if (service != null) {
            // Re-trigger connect logic in case socket died silently
            service.webSocketClient.connect()
        }
        return Result.success()
    }

    companion object {
        fun schedule(context: Context) {
            val constraints = Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build()

            val workRequest = PeriodicWorkRequestBuilder<ReconnectWorker>(15, TimeUnit.MINUTES)
                .setConstraints(constraints)
                .build()

            WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                "AriaReconnectWorker",
                ExistingPeriodicWorkPolicy.KEEP,
                workRequest
            )
        }
    }
}
