package com.example.kharazmiadmin

import okhttp3.ResponseBody
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Path
import retrofit2.http.Query
import retrofit2.http.Streaming

// ==========================================
// تمام رابط‌های API اینجا تعریف می‌شوند
// تا با تغییر یک اکتیویتی، بقیه خراب نشوند.
// ==========================================

// 1. اینترفیس قدیمی (برای حضور و غیاب و تایید کلاس)
interface InvoiceApi {
    @GET("classes/{id}/details")
    suspend fun getClassDetails(@Path("id") id: Int): ClassDetailsResponse

    @DELETE("enrollments/{enrollment_id}")
    suspend fun deleteEnrollment(@Path("enrollment_id") id: Int): SimpleResponse
}

// 2. اینترفیس جدید (برای ثبت حواله هوشمند)
data class StudentClassStatus(
    val total_amount: Long,
    val paid_to_teacher: Long,
    val paid_to_institute: Long,
    val due_to_teacher: Long,
    val due_to_institute: Long,
    val course_id: Int? = null,
    val enrollment_id: Int? = null,
    val course_title: String? = null,
    val teacher_id: Int? = null,
    val teacher_name: String? = null,
    val is_unassigned: Boolean = false,
    // O-09: باقی‌ماندهٔ شهریه و اعتبار (هر دو نامنفی) — nullable با پیش‌فرض تا اپ با پاسخ سرورِ
    // قدیمی/ناقص هم نشکند؛ مبلغ پیش‌فرض پرداخت از remaining_tuition خوانده می‌شود.
    val remaining_tuition: Long? = null,
    val credit_balance: Long? = null,
    // «این بدهی برای چند جلسه است؟» — همه nullable/پیش‌فرض‌دار: سرور قدیمی این کلیدها را نمی‌فرستد
    // (sessions_billed == null یعنی سرور به‌روز نیست).
    val course_code: String? = null,
    val sessions_billed: Int? = null,
    val sessions_held: Int? = null,
    val unpaid_sessions: Int? = null,
    val session_unit_teacher: Long? = null,
    val session_unit_institute: Long? = null,
    val session_unit_total: Long? = null,
    val contract_only: Boolean = false,
    val unpaid_session_items: List<UnpaidSessionItem>? = null
)

// یک جلسهٔ پرداخت‌نشده (قدیمی‌ترین اول) — جمع این آیتم‌ها برابر due_to_teacher / due_to_institute است
data class UnpaidSessionItem(
    val session_id: Int? = null,
    val date: String? = null,
    val remaining_teacher: Long = 0,
    val remaining_institute: Long = 0,
    val remaining_total: Long = 0
)

interface NewInvoiceApi {
    @GET("finance/search_advanced")
    suspend fun searchAdvanced(@Query("query") q: String): List<AdvancedSearchItem>

    @POST("finance/pay")
    suspend fun submitPayment(@Body data: FinanceSubmitData): FinanceResponse

    @GET("admin/students/{id}/full_profile")
    suspend fun getFullStudentProfile(@Path("id") id: Int): FullStudentProfile

    @GET("finance/student_class_status")
    suspend fun getStudentClassStatus(
        @Query("student_id") studentId: Int,
        @Query("course_id") courseId: Int?,
        @Query("course_code") courseCode: String?
    ): StudentClassStatus
}

// 3. اینترفیس‌های دیگر (اختیاری برای نظم بیشتر در آینده)
interface ClassApi {
    @GET("classes/list")
    suspend fun getAllClasses(): List<ClassListItem>

    @POST("classes/{id}/suspend")
    suspend fun suspendClass(@Path("id") id: Int): SuspendResponse

    @POST("admin/classes/{id}/suspend_s")
    suspend fun suspendClassAdmin(@Path("id") id: Int): SuspendResponse

    @POST("admin/classes/suspend_bulk")
    suspend fun suspendBulkClasses(@Body req: BulkSuspendRequest): SimpleResponse

    @PUT("classes/update")
    suspend fun updateClass(@Query("course_id") courseId: Int, @Body req: AdminClassUpdateRequest): SimpleResponse

    @POST("classes/pending_approval/bulk_approve")
    suspend fun bulkApprove(@Body req: BulkClassDecisionRequest): SimpleResponse

    @POST("classes/pending_approval/bulk_reject")
    suspend fun bulkReject(@Body req: BulkClassDecisionRequest): SimpleResponse
}

data class BulkClassDecisionRequest(val course_ids: List<Int>, val reason: String? = null)

data class AdminClassUpdateRequest(
    val title: String? = null,
    val grade_level: String? = null,
    val days_of_week: String? = null,
    val class_time: String? = null,
    val capacity: Int? = null,
    val teacher_id: Int? = null,
    val is_paused: Boolean? = null
)

// ———————————————— اقساط شهریه (A1) — سه endpoint موجود سرور بدون UI ————————————————
interface InstallmentApi {
    @POST("finance/installments")
    suspend fun createInstallment(@Body req: CreateInstallmentRequest): CreateInstallmentResponse

    @POST("finance/installments/{id}/pay")
    suspend fun payInstallment(
        @Path("id") id: Int,
        @Query("payment_method") paymentMethod: String = "نقدی",
        @Query("branch_id") branchId: Int? = null
    ): PayInstallmentResponse

    @POST("finance/installments/{id}/remind")
    suspend fun remindInstallment(@Path("id") id: Int): RemindInstallmentResponse
}

interface FinanceDashboardApi {
    @GET("finance/student/{student_id}/dashboard")
    suspend fun getFinancialDashboard(@Path("student_id") studentId: Int): FinancialDashboardResponse
}

// ==========================================
// Audit Radar - داشبورد تشخیص تقلب (Admin Only)
// ==========================================
interface AuditApi {
    @GET("audit/suspicious_patterns")
    suspend fun getSuspiciousPatterns(): List<AuditAlert>
}

// ==========================================
// Student 360 Timeline - Unified Activity Feed
// ==========================================
interface TimelineApi {
    @GET("students/{id}/timeline")
    suspend fun getTimeline(@Path("id") id: Int): List<TimelineEvent>
}

// ==========================================
// Smart Auto-Dunning - Human-in-the-Loop (Admin Only)
// ==========================================
interface DunningApi {
    @GET("dunning/drafts")
    suspend fun getDrafts(): List<DunningDraft>

    @POST("dunning/send_batch")
    suspend fun sendBatch(@Body req: DunningSendRequest): DunningSendResponse
}

// ==========================================
// Admin Command Center - Unified Dashboard (Admin Only)
// ==========================================
interface DashboardApi {
    @GET("dashboard/kpis")
    suspend fun getKPIs(): DashboardKPIs
}

// ==========================================
// Export to Excel/CSV — سه خروجی ادمین (routers/exports.py)
// FIX Export: @Streaming برای دیتاست 10k+ (بدون نگه‌داشتن کل فایل در حافظه).
// بدون پارامتر هدر: توکن Bearer به‌صورت سراسری توسط RetrofitClient تزریق می‌شود.
// ==========================================
interface ExportApi {
    @Streaming
    @GET("exports/debtors")
    suspend fun exportDebtors(): Response<ResponseBody>

    @Streaming
    @GET("exports/overdue_installments")
    suspend fun exportOverdueInstallments(): Response<ResponseBody>

    @Streaming
    @GET("exports/audit_alerts")
    suspend fun exportAuditAlerts(): Response<ResponseBody>
}

// ==========================================
// Financial Audit Trail — تاریخچه‌ی تغییرات مالی (routers/audit_trail.py)
// ==========================================
interface AuditTrailApi {
    @GET("audit-trail/logs")
    suspend fun getLogs(
        @Query("entity_type") entityType: String? = null,
        @Query("entity_id") entityId: Int? = null,
        @Query("action") action: String? = null,
        @Query("user_id") userId: Int? = null,
        @Query("start_date") startDate: String? = null,
        @Query("end_date") endDate: String? = null,
        // FIX (گروه۲/آیتم۸): جست‌وجوی نام دانش‌آموز/معلم/کلاس/شعبه/گیرنده در سرور
        @Query("search") search: String? = null,
        @Query("page") page: Int = 1,
        @Query("limit") limit: Int = 50
    ): AuditTrailResponse

    // خروجی CSV کل لاگ‌ها از همین مدل داده — بدون اندپوینت جدید سمت سرور (سرور دست‌نخورده می‌ماند).
    @Streaming
    @GET("audit-trail/logs")
    suspend fun exportLogsCsv(
        @Query("entity_type") entityType: String? = null,
        @Query("entity_id") entityId: Int? = null,
        @Query("action") action: String? = null,
        @Query("start_date") startDate: String? = null,
        @Query("end_date") endDate: String? = null,
        @Query("search") search: String? = null,
        @Query("limit") limit: Int = 200
    ): Response<ResponseBody>
}
