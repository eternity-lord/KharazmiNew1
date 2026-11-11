package com.example.kharazmiadmin

import retrofit2.http.*

// لایهٔ دادهٔ HomeworkNetworkApi: قراردادِ Retrofit این دامنه؛ از HomeworkActivity.kt بیرون کشیده شد (فاز P4d).
// هم‌بسته (same package) با بقیهٔ اپ تا هیچ call site ای به import نیاز پیدا نکند.

interface HomeworkNetworkApi {
    @POST("homework/create")
    suspend fun createHomework(@Body req: HomeworkCreateRequest): HomeworkResponseModel

    @DELETE("homework/{id}")
    suspend fun deleteHomework(@Path("id") id: Int): SimpleResponse

    @GET("homework/student/list")
    suspend fun getStudentHomeworks(): List<HomeworkItem>

    @POST("homework/submissions/{id}/grade")
    suspend fun gradeSubmission(@Path("id") subId: Int, @Body req: GradeSubmissionRequest): SimpleResponse

    @GET("homework/parent/child/{student_id}")
    suspend fun getParentChildHomeworks(@Path("student_id") studentId: Int): List<HomeworkItem>
}
