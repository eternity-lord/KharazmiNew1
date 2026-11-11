package com.example.kharazmiadmin

import retrofit2.http.Body
import retrofit2.http.POST
import retrofit2.http.GET
import retrofit2.http.PUT

// لایهٔ دادهٔ AttendanceSubmitApi: قراردادِ Retrofit این دامنه؛ از AttendanceActivity.kt بیرون کشیده شد (فاز P4d).
// هم‌بسته (same package) با بقیهٔ اپ تا هیچ call site ای به import نیاز پیدا نکند.

// API داخلی برای ثبت جلسه (بقیه از فایل ApiInterfaces خوانده می‌شوند)

interface AttendanceSubmitApi {
    @POST("attendance/submit_session")
    suspend fun submitSession(@Body data: SessionSubmitData): SessionResponse

    @GET("attendance/session/{session_code}")
    suspend fun getSessionDetails(@retrofit2.http.Path("session_code") sessionCode: Int): SessionDetailsResponse

    @PUT("attendance/session/{session_code}")
    suspend fun editSession(
        @retrofit2.http.Path("session_code") sessionCode: Int,
        @Body data: SessionSubmitData
    ): SessionResponse
}
