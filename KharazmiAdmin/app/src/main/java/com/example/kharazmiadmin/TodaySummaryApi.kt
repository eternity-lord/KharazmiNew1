package com.example.kharazmiadmin

import android.content.Context
import com.google.gson.Gson
import com.google.gson.annotations.SerializedName
import retrofit2.http.GET
import retrofit2.http.Path

// Real-time dashboard responses. These models intentionally contain no financial
// calculations; every value is rendered exactly as returned by the server.
data class AdminTodaySummary(
    val date: String = "",
    @SerializedName("day_name") val dayName: String = "",
    @SerializedName("scheduled_classes") val scheduledClasses: Int = 0,
    @SerializedName("started_classes") val startedClasses: Int = 0,
    @SerializedName("late_classes") val lateClasses: List<LateClassAlert> = emptyList(),
    @SerializedName("today_payments") val todayPayments: Long? = null,
    @SerializedName("payment_visible") val paymentVisible: Boolean = false,
    @SerializedName("today_enrollments") val todayEnrollments: Int = 0,
    @SerializedName("smart_alerts_visible") val smartAlertsVisible: Boolean = false,
    @SerializedName("teacher_settlement_alert_days") val teacherSettlementAlertDays: Int? = null,
    @SerializedName("installment_alerts") val installmentAlerts: InstallmentAlertGroup? = null,
    @SerializedName("teacher_settlement_alerts") val teacherSettlementAlerts: TeacherSettlementAlertGroup? = null
)

data class InstallmentAlertGroup(
    val count: Int = 0,
    @SerializedName("total_amount") val totalAmount: Long = 0,
    val items: List<DueInstallmentAlert> = emptyList()
)

data class DueInstallmentAlert(
    @SerializedName("installment_id") val installmentId: Int,
    @SerializedName("enrollment_id") val enrollmentId: Int,
    @SerializedName("student_id") val studentId: Int,
    @SerializedName("student_name") val studentName: String = "",
    val amount: Long = 0,
    @SerializedName("due_date") val dueDate: String = "",
    @SerializedName("days_overdue") val daysOverdue: Int = 0
)

data class TeacherSettlementAlertGroup(
    val count: Int = 0,
    @SerializedName("total_amount") val totalAmount: Long = 0,
    val items: List<TeacherSettlementAlert> = emptyList()
)

data class TeacherSettlementAlert(
    @SerializedName("teacher_id") val teacherId: Int,
    @SerializedName("teacher_name") val teacherName: String = "",
    @SerializedName("unsettled_amount") val unsettledAmount: Long = 0,
    @SerializedName("session_count") val sessionCount: Int = 0,
    @SerializedName("oldest_unsettled_date") val oldestUnsettledDate: String = "",
    @SerializedName("oldest_days_unsettled") val oldestDaysUnsettled: Int = 0,
    @SerializedName("last_settlement_at") val lastSettlementAt: String? = null
)

data class LateClassAlert(
    @SerializedName("course_id") val courseId: Int,
    @SerializedName("class_name") val className: String = "",
    @SerializedName("teacher_id") val teacherId: Int? = null,
    @SerializedName("teacher_name") val teacherName: String = "",
    @SerializedName("scheduled_time") val scheduledTime: String = "",
    @SerializedName("minutes_late") val minutesLate: Int = 0
)

data class TeacherTodaySummary(
    val date: String = "",
    @SerializedName("day_name") val dayName: String = "",
    @SerializedName("live_class") val liveClass: TeacherTodayLiveClass? = null,
    @SerializedName("next_class") val nextClass: TeacherTodayNextClass? = null,
    @SerializedName("week_summary") val weekSummary: TeacherWeekSummary = TeacherWeekSummary()
)

data class TeacherTodayLiveClass(
    @SerializedName("live_session_id") val liveSessionId: Int,
    @SerializedName("course_id") val courseId: Int,
    @SerializedName("class_name") val className: String = "",
    @SerializedName("started_at_ts") val startedAtTs: Long? = null,
    @SerializedName("elapsed_minutes") val elapsedMinutes: Int = 0
)

data class TeacherTodayNextClass(
    @SerializedName("course_id") val courseId: Int,
    @SerializedName("class_name") val className: String = "",
    @SerializedName("scheduled_time") val scheduledTime: String = "",
    @SerializedName("scheduled_date") val scheduledDate: String = "",
    @SerializedName("minutes_until") val minutesUntil: Int = 0
)

data class TeacherWeekSummary(
    @SerializedName("sessions_taught") val sessionsTaught: Int = 0,
    @SerializedName("unsettled_amount") val unsettledAmount: Long = 0
)

interface TodaySummaryApi {
    @GET("admin/today_summary")
    suspend fun getAdminTodaySummary(): AdminTodaySummary

    @GET("teachers/{id}/today_summary")
    suspend fun getTeacherTodaySummary(@Path("id") teacherId: Int): TeacherTodaySummary
}

/**
 * A deliberately short cache for moment-to-moment dashboard data.
 *
 * Unlike CachedApiCall, stale entries are never used as an offline fallback. An
 * entry older than 30 seconds is ignored so a live/late class cannot remain on
 * screen because of the app's normal long-lived cache behavior.
 */
object TodaySummaryShortCache {
    private const val TTL_MILLIS = 30_000L

    suspend fun <T> getOrFetch(
        context: Context,
        key: String,
        modelClass: Class<T>,
        forceRefresh: Boolean = false,
        networkCall: suspend () -> T
    ): T {
        if (!forceRefresh) {
            val (cachedJson, timestamp) = CacheManager.get(context, key)
            val isFresh = cachedJson != null &&
                timestamp > 0L &&
                System.currentTimeMillis() - timestamp <= TTL_MILLIS
            if (isFresh) {
                try {
                    return Gson().fromJson(cachedJson, modelClass)
                } catch (_: Exception) {
                    CacheManager.clear(context, key)
                }
            } else if (cachedJson != null) {
                CacheManager.clear(context, key)
            }
        }

        val fresh = networkCall()
        CacheManager.save(context, key, Gson().toJson(fresh))
        return fresh
    }
}
