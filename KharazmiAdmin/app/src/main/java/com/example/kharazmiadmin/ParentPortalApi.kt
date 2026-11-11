package com.example.kharazmiadmin

import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST

// لایهٔ دادهٔ ParentPortalApi: قراردادِ Retrofit این دامنه؛ از ParentPortalActivity.kt بیرون کشیده شد (فاز P4d).
// هم‌بسته (same package) با بقیهٔ اپ تا هیچ call site ای به import نیاز پیدا نکند.

interface ParentPortalApi {
    @POST("parent/request_otp")
    suspend fun requestOtp(@Body req: ParentOtpRequest): SimpleResponse

    @POST("parent/login")
    suspend fun parentLogin(@Body req: ParentLoginRequest): ParentLoginResponse

    @POST("parent/select_child")
    suspend fun selectChild(@Body req: ChildSelectRequest): ParentLoginResponse

    @GET("parent/child_profile")
    suspend fun getChildProfile(): ParentProfileResponse
}
