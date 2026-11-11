package com.example.kharazmiadmin

import retrofit2.http.DELETE
import retrofit2.http.POST
import retrofit2.http.Path

// لایهٔ دادهٔ TeacherManagementApi: قراردادِ Retrofit این دامنه؛ از TeacherProfileActivity.kt بیرون کشیده شد (فاز P4d).
// هم‌بسته (same package) با بقیهٔ اپ تا هیچ call site ای به import نیاز پیدا نکند.

interface TeacherManagementApi {
    @POST("/admin/teachers/{teacher_id}/suspend")
    suspend fun suspendTeacher(@Path("teacher_id") teacherId: Int): SuspendResponse

    @DELETE("/admin/teachers/{teacher_id}")
    suspend fun deleteTeacher(@Path("teacher_id") teacherId: Int): SimpleResponse
}
