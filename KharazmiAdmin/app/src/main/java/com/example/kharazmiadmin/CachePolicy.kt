package com.example.kharazmiadmin

// FIX: Bug 20 - persisted entries expire after five minutes, including offline fallback reads.
object CachePolicy {
    const val TTL_MILLIS = 5 * 60 * 1000L

    fun isFresh(timestamp: Long, now: Long = System.currentTimeMillis(), ttlMillis: Long = TTL_MILLIS): Boolean =
        timestamp > 0 && ttlMillis > 0 && now >= timestamp && now - timestamp < ttlMillis
}

