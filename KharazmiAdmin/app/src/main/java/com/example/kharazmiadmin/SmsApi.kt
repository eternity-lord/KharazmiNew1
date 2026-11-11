package com.example.kharazmiadmin

import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST

// لایهٔ دادهٔ SmsApi: قراردادِ Retrofit این دامنه؛ از SmsActivity.kt بیرون کشیده شد (فاز P4d).
// هم‌بسته (same package) با بقیهٔ اپ تا هیچ call site ای به import نیاز پیدا نکند.

interface SmsApi {
    @POST("sms/send")
    suspend fun sendSms(@Body req: SmsRequest): SmsResponse

    @GET("sms/history")
    suspend fun getHistory(): List<SmsLogItem>
}
