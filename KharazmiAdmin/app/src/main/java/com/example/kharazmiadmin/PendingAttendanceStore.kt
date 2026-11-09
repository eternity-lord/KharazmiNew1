package com.example.kharazmiadmin

import android.content.Context
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import java.io.File
import java.util.UUID

/**
 * FIX C10-B2: durable outbox for attendance submissions that failed with network errors.
 *
 * Same style as CacheManager (object, Gson, one JSON file, never-throwing reads) with two
 * deliberate upgrades a queue needs but a cache does not:
 *  - filesDir instead of cacheDir (the OS may delete cacheDir; queued work must survive).
 *  - atomic tmp+rename writes (a crash mid-write must never leave a half-written queue).
 * All access is synchronized; every public fun is safe to call from any thread.
 */
object PendingAttendanceStore {

    enum class Op { SUBMIT, EDIT }
    enum class Status { PENDING, SENDING, FAILED }

    data class PendingStudent(val student_id: Int, val status: String, val excused: Boolean = false)

    data class PendingItem(
        val id: String = UUID.randomUUID().toString(),
        val op: Op = Op.SUBMIT,
        val targetSessionCode: Int? = null, // EDIT only
        val courseId: Int = -1,
        val className: String? = null, // display only (B3 card); null when unknown
        val date: String = "",
        val items: List<PendingStudent> = emptyList(),
        val tries: Int = 0,
        val status: Status = Status.PENDING,
        val lastError: String? = null,
        val createdAt: Long = System.currentTimeMillis()
    )

    private const val FILE_NAME = "pending_attendance.json"
    private val gson = Gson()
    private val lock = Any()

    private fun getFile(context: Context): File = File(context.filesDir, FILE_NAME)

    private fun readAllUnsafe(context: Context): MutableList<PendingItem> {
        val file = getFile(context)
        if (!file.exists()) return mutableListOf()
        return try {
            val type = object : TypeToken<MutableList<PendingItem>>() {}.type
            gson.fromJson<MutableList<PendingItem>>(file.readText(Charsets.UTF_8), type) ?: mutableListOf()
        } catch (e: Exception) {
            android.util.Log.e("PendingAttendanceStore", "readAllUnsafe failed", e)
            mutableListOf() // corrupt file → start fresh (never crash the submit path)
        }
    }

    private fun writeAllUnsafe(context: Context, items: List<PendingItem>) {
        val file = getFile(context)
        val tmp = File(context.filesDir, "$FILE_NAME.tmp")
        tmp.writeText(gson.toJson(items), Charsets.UTF_8)
        // Atomic replace: readers never see a half-written file.
        if (!tmp.renameTo(file)) {
            tmp.copyTo(file, overwrite = true)
            tmp.delete()
        }
    }

    fun add(context: Context, item: PendingItem): PendingItem = synchronized(lock) {
        val all = readAllUnsafe(context)
        all.add(item)
        writeAllUnsafe(context, all)
        item
    }

    fun getAll(context: Context): List<PendingItem> = synchronized(lock) {
        readAllUnsafe(context).toList()
    }

    fun updateStatus(
        context: Context,
        id: String,
        status: Status,
        error: String? = null,
        incTries: Boolean = false
    ) {
        synchronized(lock) {
            val all = readAllUnsafe(context)
            val i = all.indexOfFirst { it.id == id }
            if (i >= 0) {
                val cur = all[i]
                all[i] = cur.copy(
                    status = status,
                    lastError = error ?: cur.lastError,
                    tries = cur.tries + if (incTries) 1 else 0
                )
                writeAllUnsafe(context, all)
            }
        }
    }

    fun remove(context: Context, id: String) {
        synchronized(lock) {
            val all = readAllUnsafe(context)
            if (all.removeAll { it.id == id }) writeAllUnsafe(context, all)
        }
    }
}
