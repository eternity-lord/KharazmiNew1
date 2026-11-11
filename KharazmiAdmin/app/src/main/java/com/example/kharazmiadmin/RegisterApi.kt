package com.example.kharazmiadmin

import retrofit2.http.Body
import retrofit2.http.POST
import retrofit2.http.GET

// لایهٔ دادهٔ RegisterApi: قراردادِ Retrofit این دامنه؛ از StudentRegisterActivity.kt بیرون کشیده شد (فاز P4d).
// هم‌بسته (same package) با بقیهٔ اپ تا هیچ call site ای به import نیاز پیدا نکند.

// ==========================================
// API Interfaces
// ==========================================

interface RegisterApi {
    @POST("students/register_and_enroll")
    suspend fun registerAndEnrollStudent(@Body data: StudentRegisterAndEnrollRequest): RegisterResponse

    @GET("classes/list")
    suspend fun getClassesList(): List<ClassListItem>
}
