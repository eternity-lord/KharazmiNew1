package com.example.kharazmiadmin

import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST

// لایهٔ دادهٔ StudentPortalApi: قراردادِ Retrofit این دامنه؛ از StudentPortalActivity.kt بیرون کشیده شد (فاز P4d).
// هم‌بسته (same package) با بقیهٔ اپ تا هیچ call site ای به import نیاز پیدا نکند.

interface StudentPortalApi {
    @POST("auth/student/request_otp")
    suspend fun requestOtp(@Body req: StudentOtpRequest): SimpleResponse

    @POST("auth/student/login")
    suspend fun studentLogin(@Body req: StudentLoginRequest): StudentLoginResponse

    @GET("students/my_profile")
    suspend fun getStudentProfile(): ParentProfileResponse
}
