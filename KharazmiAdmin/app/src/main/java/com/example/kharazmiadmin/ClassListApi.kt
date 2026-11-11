package com.example.kharazmiadmin

import retrofit2.http.GET
import retrofit2.http.Path

// لایهٔ دادهٔ ClassListApi: قراردادِ Retrofit این دامنه؛ از ClassSetupActivity.kt بیرون کشیده شد (فاز P4d).
// هم‌بسته (same package) با بقیهٔ اپ تا هیچ call site ای به import نیاز پیدا نکند.

interface ClassListApi {
    @GET("classes/{id}/details")
    suspend fun getClassDetails(@Path("id") id: Int): ClassDetailsResponse
}
