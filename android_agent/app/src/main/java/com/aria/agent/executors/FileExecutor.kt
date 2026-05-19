package com.aria.agent.executors

import android.util.Base64
import com.aria.agent.AriaAccessibilityService
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.net.URLConnection

class FileExecutor(private val service: AriaAccessibilityService) {

    fun readFile(path: String): JSONObject {
        return try {
            val file = File(path)
            if (!file.exists()) return errorJson("File not found")
            
            val bytes = file.readBytes()
            val b64 = Base64.encodeToString(bytes, Base64.NO_WRAP)
            val mimeType = URLConnection.guessContentTypeFromName(path) ?: "application/octet-stream"
            
            JSONObject().apply {
                put("content_b64", b64)
                put("size_bytes", bytes.size)
                put("mime_type", mimeType)
                put("name", file.name)
            }
        } catch (e: SecurityException) {
            errorJson("Permission denied")
        } catch (e: Exception) {
            errorJson(e.message ?: "Unknown error")
        }
    }

    fun writeFile(path: String, contentB64: String): JSONObject {
        return try {
            val bytes = Base64.decode(contentB64, Base64.NO_WRAP)
            val file = File(path)
            file.parentFile?.mkdirs()
            file.writeBytes(bytes)
            
            JSONObject().apply {
                put("status", "ok")
                put("bytes_written", bytes.size)
                put("path", path)
            }
        } catch (e: Exception) {
            errorJson(e.message ?: "Unknown error")
        }
    }

    fun listFiles(path: String, recursive: Boolean): JSONObject {
        return try {
            val dir = File(path)
            if (!dir.exists() || !dir.isDirectory) return errorJson("Not a directory")
            
            val files = if (recursive) dir.walkTopDown() else dir.listFiles()?.asSequence()
            val jsonArray = JSONArray()
            
            files?.forEach { f ->
                jsonArray.put(JSONObject().apply {
                    put("name", f.name)
                    put("path", f.absolutePath)
                    put("size", if (f.isFile) f.length() else 0)
                    put("is_dir", f.isDirectory)
                    put("modified", f.lastModified())
                })
            }
            
            JSONObject().apply {
                put("files", jsonArray)
                put("count", jsonArray.length())
            }
        } catch (e: Exception) {
            errorJson(e.message ?: "Unknown error")
        }
    }

    fun deleteFile(path: String): JSONObject {
        val deleted = File(path).delete()
        return JSONObject().apply {
            put("status", if (deleted) "ok" else "error")
            put("path", path)
        }
    }

    private fun errorJson(msg: String): JSONObject {
        return JSONObject().apply { put("error", msg) }
    }
}
