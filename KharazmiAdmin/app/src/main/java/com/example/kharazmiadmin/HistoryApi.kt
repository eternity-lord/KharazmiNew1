package com.example.kharazmiadmin

import retrofit2.http.Body
import retrofit2.http.POST

// لایهٔ دادهٔ HistoryApi: قراردادِ Retrofit این دامنه؛ از SessionHistoryActivity.kt بیرون کشیده شد (فاز P4d).
// هم‌بسته (same package) با بقیهٔ اپ تا هیچ call site ای به import نیاز پیدا نکند.

// API

interface HistoryApi {
    @POST("attendance/get_history")
    suspend fun getHistory(@Body req: HistoryRequest): List<SessionHistoryItem>
}
