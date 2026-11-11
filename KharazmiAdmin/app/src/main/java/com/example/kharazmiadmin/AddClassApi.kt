package com.example.kharazmiadmin

import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST

// لایهٔ دادهٔ AddClassApi: قراردادِ Retrofit این دامنه؛ از AddClassActivity.kt بیرون کشیده شد (فاز P4d).
// هم‌بسته (same package) با بقیهٔ اپ تا هیچ call site ای به import نیاز پیدا نکند.

// API

interface AddClassApi {
    @GET("teachers/list")
    suspend fun getTeachers(): List<TeacherSimple>

    @POST("classes/create")
    suspend fun createClass(
        @Body data: ClassSubmitData,
        @retrofit2.http.Query("override") override: Boolean = false
    ): ClassResponse
}
