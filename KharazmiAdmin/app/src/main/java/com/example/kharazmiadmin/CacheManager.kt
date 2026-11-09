package com.example.kharazmiadmin

import android.content.Context
import com.google.gson.Gson
import java.io.File

object CacheManager {

    // ساختار ذخیره اطلاعات کش فیزیکی
    private data class CacheEntry(val data: String, val timestamp: Long)

    // ایجاد یک نام فایل کاملاً امن و پاک‌سازی شده از کاراکترهای غیرمجاز لینوکس/اندروید
    private fun getFile(context: Context, key: String): File {
        val safeName = key.replace("[^a-zA-Z0-9_.-]".toRegex(), "_") + ".cache"
        return File(context.cacheDir, safeName)
    }

    // ذخیره مستقیم تصویر JSON و برچسب زمان در یک فایل جداگانه در cacheDir
    fun save(context: Context, key: String, data: String) {
        try {
            val file = getFile(context, key)
            val entry = CacheEntry(data, System.currentTimeMillis())
            val json = Gson().toJson(entry)
            file.writeText(json, Charsets.UTF_8)
        } catch (e: Exception) {
            android.util.Log.e("CacheManager", "save failed", e)
        }
    }

    // خواندن فایل کش در صورت وجود (امن در برابر نبود فایل یا حذف توسط سیستم‌عامل)
    fun get(context: Context, key: String): Pair<String?, Long> {
        return try {
            val file = getFile(context, key)
            if (file.exists()) {
                val json = file.readText(Charsets.UTF_8)
                val entry = Gson().fromJson(json, CacheEntry::class.java)
                // FIX: Bug 20 - reject expired, legacy/undated and future-dated cache entries.
                if (CachePolicy.isFresh(entry.timestamp)) {
                    Pair(entry.data, entry.timestamp)
                } else {
                    file.delete()
                    Pair(null, 0L)
                }
            } else {
                Pair(null, 0L)
            }
        } catch (e: Exception) {
            android.util.Log.e("CacheManager", "get failed", e)
            Pair(null, 0L)
        }
    }

    // حذف یک فایل کش تکی
    fun clear(context: Context, key: String) {
        try {
            val file = getFile(context, key)
            if (file.exists()) {
                file.delete()
            }
        } catch (e: Exception) {
            android.util.Log.e("CacheManager", "clear failed", e)
        }
    }

    // حذف گروهی فایل‌های کش بر اساس پیشوند کلمات پاک‌سازی شده
    fun clearByPrefix(context: Context, prefix: String) {
        try {
            val safePrefix = prefix.replace("[^a-zA-Z0-9_.-]".toRegex(), "_")
            val cacheDir = context.cacheDir
            val files = cacheDir.listFiles()
            if (files != null) {
                for (file in files) {
                    if (file.name.startsWith(safePrefix) && file.name.endsWith(".cache")) {
                        file.delete()
                    }
                }
            }
        } catch (e: Exception) {
            android.util.Log.e("CacheManager", "clearByPrefix failed", e)
        }
    }
}
