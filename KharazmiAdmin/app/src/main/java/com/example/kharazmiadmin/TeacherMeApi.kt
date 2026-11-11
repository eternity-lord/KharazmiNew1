package com.example.kharazmiadmin

import retrofit2.http.GET

// لایهٔ دادهٔ TeacherMeApi: قراردادِ Retrofit این دامنه؛ از TeacherDashboardActivity.kt بیرون کشیده شد (فاز P4d).
// هم‌بسته (same package) با بقیهٔ اپ تا هیچ call site ای به import نیاز پیدا نکند.

interface TeacherMeApi {
    @GET("auth/me")
    suspend fun getMe(): MeResponse
}
