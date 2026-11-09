package com.example.kharazmiadmin

// ==========================================
// 🎥 رابط‌های API برای کلاس‌های زنده (Live Sessions)
// همه‌ی endpoint های جدید اینجا تعریف می‌شوند تا اکتیویتی‌ها تمیز بمانند.
// ==========================================

interface LiveApi {

    // --- معلم ---
    // شروع کلاس زنده برای یک کلاس (course_id)
    @retrofit2.http.POST("attendance/{course_id}/start_live")
    suspend fun startLive(
        @retrofit2.http.Path("course_id") courseId: Int
    ): LiveStartResponse

    // ذخیره‌ی وضعیت لحظه‌ای (چه جزئی چه کامل) — همگام‌سازی پیشینه‌ای
    @retrofit2.http.POST("attendance/{session_id}/live_status")
    suspend fun saveLiveStatus(
        @retrofit2.http.Path("session_id") sessionId: Int,
        @retrofit2.http.Body body: LiveStatusPayload
    ): SimpleResponse

    // پایان کلاس زنده (اجرای محاسبه مالی روی زیرساخت موجود)
    @retrofit2.http.POST("attendance/{session_id}/end_live")
    suspend fun endLive(
        @retrofit2.http.Path("session_id") sessionId: Int,
        @retrofit2.http.Body body: LiveEndPayload
    ): LiveEndResponse

    // لغو کلاس زنده — فقط وضعیت LiveSession را می‌بندد و هیچ جلسه/حضور/تراکنشی نمی‌سازد.
    @retrofit2.http.POST("attendance/{session_id}/cancel_live")
    suspend fun cancelLive(
        @retrofit2.http.Path("session_id") sessionId: Int
    ): LiveCancelResponse

    // جلسه‌ی زنده‌ی فعلیِ معلمِ لاگین‌شده (برای رزومه/تایمر)
    @retrofit2.http.GET("attendance/live/current")
    suspend fun getCurrentLive(): LiveCurrentResponse?

    // --- ادمین/منشی ---
    // لیست کلاس‌های زنده
    @retrofit2.http.GET("admin/live_sessions")
    suspend fun getLiveSessions(): List<LiveSessionItem>

    // جزئیات لحظه‌ای یک کلاس زنده (روستر + شماره تماس)
    @retrofit2.http.GET("admin/live_sessions/{session_id}/roster")
    suspend fun getLiveRoster(
        @retrofit2.http.Path("session_id") sessionId: Int
    ): LiveRosterResponse
}

// بدنه‌ی ذخیره‌ی وضعیت لحظه‌ای: { student_id : { status, excused } }
data class LiveStatusPayload(
    val items: Map<String, LiveStatusEntry>
)

data class LiveStatusEntry(
    val status: String = "Present",
    val excused: Boolean = false
)

// بدنه‌ی پایان کلاس زنده (اختیاری — تاریخ سفارشی)
data class LiveEndPayload(
    val date: String? = null
)
