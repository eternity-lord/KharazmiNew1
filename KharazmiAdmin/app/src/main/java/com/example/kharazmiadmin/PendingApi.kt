package com.example.kharazmiadmin

import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path

// لایهٔ دادهٔ PendingApi: قراردادِ Retrofit این دامنه؛ از PendingTeachersActivity.kt بیرون کشیده شد (فاز P4d).
// هم‌بسته (same package) با بقیهٔ اپ تا هیچ call site ای به import نیاز پیدا نکند.

interface PendingApi {
    @GET("teachers/pending")
    suspend fun getPendingTeachers(): List<TeacherPending>

    @POST("teachers/approve/{id}")
    suspend fun approveTeacher(@Path("id") id: Int): ApproveResponse

    // ❌ متد جدید برای رد کردن (حذف) معلم
    @DELETE("teachers/reject/{id}")
    suspend fun rejectTeacher(@Path("id") id: Int): ApproveResponse
}
