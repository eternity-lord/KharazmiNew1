package com.example.kharazmiadmin

import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST

// لایهٔ دادهٔ ShareApi: قراردادِ Retrofit این دامنه؛ از ShareConfigActivity.kt بیرون کشیده شد (فاز P4d).
// هم‌بسته (same package) با بقیهٔ اپ تا هیچ call site ای به import نیاز پیدا نکند.

// API

interface ShareApi {
    @GET("config/share")
    suspend fun getShares(): ShareConfigData

    @POST("config/share/update")
    suspend fun updateShares(@Body data: ShareConfigData): SimpleResponse
}
