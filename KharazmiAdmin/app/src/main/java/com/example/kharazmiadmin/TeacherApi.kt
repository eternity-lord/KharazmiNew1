package com.example.kharazmiadmin

import retrofit2.http.Body
import retrofit2.http.POST

// لایهٔ دادهٔ TeacherApi: قراردادِ Retrofit این دامنه؛ از TeacherRegisterActivity.kt بیرون کشیده شد (فاز P4d).
// هم‌بسته (same package) با بقیهٔ اپ تا هیچ call site ای به import نیاز پیدا نکند.

// ==========================================
// API Interface
// ==========================================

interface TeacherApi {
    @POST("teachers/register")
    suspend fun registerTeacher(@Body data: TeacherRegisterData): RegisterResponse
}
