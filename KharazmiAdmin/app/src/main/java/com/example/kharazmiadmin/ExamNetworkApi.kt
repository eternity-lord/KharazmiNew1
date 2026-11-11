package com.example.kharazmiadmin

import retrofit2.http.*

// لایهٔ دادهٔ ExamNetworkApi: قراردادِ Retrofit این دامنه؛ از ExamActivity.kt بیرون کشیده شد (فاز P4d).
// هم‌بسته (same package) با بقیهٔ اپ تا هیچ call site ای به import نیاز پیدا نکند.

interface ExamNetworkApi {
    @GET("exams/student/list")
    suspend fun getExams(): List<HomeworkItem>

    @POST("exams/attempts/{exam_id}/start")
    suspend fun startAttempt(@Path("exam_id") examId: Int): AttemptStartResponse

    @POST("exams/attempts/{attempt_id}/submit")
    suspend fun submitAttempt(@Path("attempt_id") attemptId: Int, @Body req: AttemptSubmitRequest): AttemptSubmitResponse

    @GET("students/{id}/report_card")
    suspend fun getReportCard(@Path("id") id: Int): ReportCardResponse
}
