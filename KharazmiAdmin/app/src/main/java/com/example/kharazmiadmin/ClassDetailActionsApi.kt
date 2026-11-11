package com.example.kharazmiadmin

import retrofit2.http.Path
import retrofit2.http.POST
import retrofit2.http.Query
import retrofit2.http.DELETE
import retrofit2.http.PUT
import retrofit2.http.Body

// لایهٔ دادهٔ ClassDetailActionsApi: قراردادِ Retrofit این دامنه؛ از ClassDetailActivity.kt بیرون کشیده شد (فاز P4d).
// هم‌بسته (same package) با بقیهٔ اپ تا هیچ call site ای به import نیاز پیدا نکند.

interface ClassDetailActionsApi {
    @DELETE("classes/{course_id}")
    suspend fun deleteClass(
        @Path("course_id") courseId: Int,
        @Query("forgive_session_charges") forgive: Boolean
    ): SimpleResponse

    @POST("classes/{course_id}/request_delete")
    suspend fun requestDeleteClass(
        @Path("course_id") courseId: Int,
        @Body req: DeleteClassRequest
    ): SimpleResponse

    @POST("classes/{course_id}/suspend")
    suspend fun suspendClass(@Path("course_id") courseId: Int): SuspendResponse

    @PUT("classes/update_info/{course_id}")
    suspend fun updateClassInfo(@Path("course_id") courseId: Int, @Body data: ClassUpdateInfo): SimpleResponse

    @PUT("classes/update")
    suspend fun updateClass(@Query("course_id") courseId: Int, @Body data: AdminClassUpdateRequest): SimpleResponse
}
