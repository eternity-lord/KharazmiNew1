package com.example.kharazmiadmin

import okhttp3.ResponseBody
import retrofit2.Response
import retrofit2.http.GET
import retrofit2.http.Query
import retrofit2.http.Streaming

// لایهٔ دادهٔ ReportNewApi: قراردادِ Retrofit این دامنه؛ از ReportActivity.kt بیرون کشیده شد (فاز P4d).
// هم‌بسته (same package) با بقیهٔ اپ تا هیچ call site ای به import نیاز پیدا نکند.

interface ReportNewApi {
    @GET("teachers/list")
    suspend fun getTeachersList(): List<TeacherItem>

    @Streaming
    @GET("reports/financial/excel")
    suspend fun exportFinancial(
        @Query("start_date") startDate: String?,
        @Query("end_date") endDate: String?,
        @Query("branch_id") branchId: Int? = null,
        @Query("teacher_id") teacherId: Int? = null
    ): Response<ResponseBody>

    @GET("reports/financial_summary")
    suspend fun getFinancialSummary(
        @Query("user_type") userType: String,
        @Query("teacher_id") teacherId: Int?,
        @Query("year") year: Int?,
        @Query("month") month: Int?
    ): FinancialSummaryResponse

    @GET("finance/search_advanced")
    suspend fun searchAdvanced(
        @Query("query") query: String
    ): List<SearchStudentItem>

    @GET("reports/student_statement")
    suspend fun getStudentStatement(
        @Query("student_id") studentId: Int
    ): StudentStatementResponse
}
