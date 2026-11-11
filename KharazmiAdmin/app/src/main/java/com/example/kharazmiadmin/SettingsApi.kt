package com.example.kharazmiadmin

import retrofit2.http.Body
import retrofit2.http.POST

// لایهٔ دادهٔ SettingsApi: قراردادِ Retrofit این دامنه؛ از SettingsActivity.kt بیرون کشیده شد (فاز P4d).
// هم‌بسته (same package) با بقیهٔ اپ تا هیچ call site ای به import نیاز پیدا نکند.

interface SettingsApi {
    @POST("auth/change-password")
    suspend fun changePassword(@Body req: ChangePasswordRequest): SimpleResponse

    @POST("auth/change-mobile")
    suspend fun changeMobile(@Body req: ChangeMobileRequest): SimpleResponse
}
