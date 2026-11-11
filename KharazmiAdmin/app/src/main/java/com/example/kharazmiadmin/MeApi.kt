package com.example.kharazmiadmin

import retrofit2.http.GET

// لایهٔ دادهٔ MeApi: قراردادِ Retrofit این دامنه؛ از MainActivity.kt بیرون کشیده شد (فاز P4d).
// هم‌بسته (same package) با بقیهٔ اپ تا هیچ call site ای به import نیاز پیدا نکند.

interface MeApi {
    @GET("auth/me")
    suspend fun getMe(): MeResponse
}
