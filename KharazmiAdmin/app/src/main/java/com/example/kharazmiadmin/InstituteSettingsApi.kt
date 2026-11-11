package com.example.kharazmiadmin

import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.PUT

// لایهٔ دادهٔ InstituteSettingsApi: قراردادِ Retrofit این دامنه؛ از InstituteSettingsActivity.kt بیرون کشیده شد (فاز P4d).
// هم‌بسته (same package) با بقیهٔ اپ تا هیچ call site ای به import نیاز پیدا نکند.

// API Interface

interface InstituteSettingsApi {
    @GET("admin/institute_settings")
    suspend fun getSettings(): InstituteSettings

    @PUT("admin/institute_settings")
    suspend fun updateSettings(@Body data: InstituteSettings): SimpleResponse

    @retrofit2.http.Multipart
    @POST("admin/institute_settings/upload_logo")
    suspend fun uploadLogo(
        @retrofit2.http.Part file: okhttp3.MultipartBody.Part
    ): SimpleResponse
}
