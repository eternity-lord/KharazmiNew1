package com.example.kharazmiadmin

import retrofit2.http.GET

// لایهٔ دادهٔ DashboardSettingsApi: قراردادِ Retrofit این دامنه؛ از MainActivity.kt بیرون کشیده شد (فاز P4d).
// هم‌بسته (same package) با بقیهٔ اپ تا هیچ call site ای به import نیاز پیدا نکند.

// ==========================================
// API Definitions
// ==========================================

interface DashboardSettingsApi {
    @GET("admin/institute_settings")
    suspend fun getSettings(): SettingsResponse
}
