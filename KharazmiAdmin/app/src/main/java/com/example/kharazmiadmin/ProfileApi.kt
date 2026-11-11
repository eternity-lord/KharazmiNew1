package com.example.kharazmiadmin

import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Path

// لایهٔ دادهٔ ProfileApi: قراردادِ Retrofit این دامنه؛ از StudentProfileActivity.kt بیرون کشیده شد (فاز P4d).
// هم‌بسته (same package) با بقیهٔ اپ تا هیچ call site ای به import نیاز پیدا نکند.

// ==========================================
// 2. Unified Profile API (Updated)
// ==========================================

interface ProfileApi {
    // --- Student View (Full) ---
    @GET("admin/students/{id}/full_profile")
    suspend fun getFullStudentProfile(@Path("id") id: Int): FullStudentProfile

    @GET("students/{id}/grades")
    suspend fun getStudentGrades(@Path("id") id: Int): StudentGradesResponse

    @GET("students/{id}")
    suspend fun getStudentProfile(@Path("id") id: Int): StudentRawProfile

    @PUT("students/update/{id}")
    suspend fun updateStudent(@Path("id") id: Int, @Body data: StudentUpdate): SimpleResponse

    // --- Management ---
    @DELETE("admin/students/{id}")
    suspend fun deleteStudent(@Path("id") id: Int): SimpleResponse

    @POST("admin/students/{id}/toggle_suspend")
    suspend fun toggleSuspend(@Path("id") id: Int): SuspendResponse

    // --- Teacher View (Full) ---
    @GET("teachers/{id}/full_profile")
    suspend fun getFullTeacherProfile(@Path("id") id: Int): FullTeacherProfile

    @GET("teachers/{id}")
    suspend fun getTeacherProfile(@Path("id") id: Int): TeacherRawProfile

    @PUT("teachers/update/{id}") // ✅ اضافه شد برای EditTeacherActivity
    suspend fun updateTeacher(@Path("id") id: Int, @Body data: TeacherUpdate): SimpleResponse

    @retrofit2.http.Multipart
    @POST("students/{id}/upload_photo")
    suspend fun uploadStudentPhoto(
        @Path("id") id: Int,
        @retrofit2.http.Part file: okhttp3.MultipartBody.Part
    ): SimpleResponse

    @retrofit2.http.Multipart
    @POST("teachers/{id}/upload_photo")
    suspend fun uploadTeacherPhoto(
        @Path("id") id: Int,
        @retrofit2.http.Part file: okhttp3.MultipartBody.Part
    ): SimpleResponse

    @GET("teachers/{id}/pending_settlement")
    suspend fun getPendingSettlement(@Path("id") id: Int): TeacherPendingSettlementResponse

    @POST("teachers/{id}/settle")
    suspend fun settleTeacherSessions(@Path("id") id: Int, @Body req: SettleRequest): TeacherSettlementResponse

    @GET("teachers/{id}/settlement_history")
    suspend fun getSettlementHistory(@Path("id") id: Int): List<SettlementHistoryItem>

    @GET("students/{id}/installments")
    suspend fun getStudentInstallments(@Path("id") id: Int): List<StudentInstallmentItem>

    @GET("students/{id}/communication_history")
    suspend fun getStudentCommunicationHistory(
        @Path("id") id: Int
    ): List<CommunicationHistoryItem>

    @GET("teachers/{id}/communication_history")
    suspend fun getTeacherCommunicationHistory(
        @Path("id") id: Int
    ): List<CommunicationHistoryItem>

    @POST("admin/students/{id}/send_portal_link")
    suspend fun sendPortalLink(@Path("id") id: Int): SimpleResponse

    @GET("teachers/{id}/collaboration_summary")
    suspend fun getTeacherCollaborationSummary(
        @Path("id") id: Int
    ): TeacherCollaborationSummary
}
