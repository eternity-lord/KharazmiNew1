package com.example.kharazmiadmin

import retrofit2.http.Body
import retrofit2.http.POST

// لایهٔ دادهٔ GradeApi: قراردادِ Retrofit این دامنه؛ از SubmitGradeActivity.kt بیرون کشیده شد (فاز P4d).
// هم‌بسته (same package) با بقیهٔ اپ تا هیچ call site ای به import نیاز پیدا نکند.

interface GradeApi {
    @POST("grades/submit")
    suspend fun submitGrade(@Body data: GradeSubmitData): SimpleResponse
}
