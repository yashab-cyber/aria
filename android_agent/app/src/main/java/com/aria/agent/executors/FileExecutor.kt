package com.aria.agent.executors

import android.util.Base64
import com.aria.agent.AriaAccessibilityService
import java.io.File
import java.nio.file.Files
import java.nio.file.Paths

class FileExecutor(private val service: AriaAccessibilityService) {

    fun readFile(params: Map<String, Any>): Map<String, Any?> {
        val path = params["path"] as? String ?: return mapOf("status" to "error", "message" to "path required")
        
        return try {
            val file = File(path)
            if (!file.exists() || !file.isFile) return mapOf("status" to "error", "message" to "file not found")
            
            val bytes = file.readBytes()
            val b64 = Base64.encodeToString(bytes, Base64.NO_WRAP)
            var mime = "application/octet-stream"
            try {
                mime = Files.probeContentType(Paths.get(path)) ?: mime
            } catch (e: Exception) {}
            
            mapOf("content_b64" to b64, "size_bytes" to bytes.size, "mime_type" to mime)
        } catch (e: SecurityException) {
            mapOf("status" to "error", "message" to "permission denied")
        } catch (e: Exception) {
            mapOf("status" to "error", "message" to e.message)
        }
    }

    fun writeFile(params: Map<String, Any>): Map<String, Any?> {
        val path = params["path"] as? String ?: return mapOf("status" to "error", "message" to "path required")
        val b64 = params["content_b64"] as? String ?: return mapOf("status" to "error", "message" to "content_b64 required")
        
        return try {
            val bytes = Base64.decode(b64, Base64.NO_WRAP)
            val file = File(path)
            file.parentFile?.mkdirs()
            file.writeBytes(bytes)
            
            mapOf("status" to "ok", "bytes_written" to bytes.size)
        } catch (e: SecurityException) {
            mapOf("status" to "error", "message" to "permission denied")
        } catch (e: Exception) {
            mapOf("status" to "error", "message" to e.message)
        }
    }

    fun listFiles(params: Map<String, Any>): Map<String, Any?> {
        val path = params["path"] as? String ?: return mapOf("status" to "error", "message" to "path required")
        
        return try {
            val dir = File(path)
            if (!dir.exists() || !dir.isDirectory) return mapOf("status" to "error", "message" to "directory not found")
            
            val files = dir.listFiles()?.map {
                mapOf(
                    "name" to it.name,
                    "path" to it.absolutePath,
                    "size" to it.length(),
                    "is_dir" to it.isDirectory,
                    "modified" to it.lastModified()
                )
            } ?: emptyList()
            
            mapOf("files" to files)
        } catch (e: SecurityException) {
            mapOf("status" to "error", "message" to "permission denied")
        } catch (e: Exception) {
            mapOf("status" to "error", "message" to e.message)
        }
    }

    fun deleteFile(params: Map<String, Any>): Map<String, Any?> {
        val path = params["path"] as? String ?: return mapOf("status" to "error", "message" to "path required")
        
        return try {
            val file = File(path)
            if (file.exists()) {
                val deleted = if (file.isDirectory) file.deleteRecursively() else file.delete()
                mapOf("status" to if (deleted) "ok" else "error")
            } else {
                mapOf("status" to "ok") // Already gone
            }
        } catch (e: SecurityException) {
            mapOf("status" to "error", "message" to "permission denied")
        } catch (e: Exception) {
            mapOf("status" to "error", "message" to e.message)
        }
    }
}
