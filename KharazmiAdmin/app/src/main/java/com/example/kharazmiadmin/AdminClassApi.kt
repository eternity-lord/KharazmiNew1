package com.example.kharazmiadmin

import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

// لایهٔ دادهٔ AdminClassApi: قراردادِ Retrofit این دامنه؛ از PendingClassesActivity.kt بیرون کشیده شد (فاز P4d).
// هم‌بسته (same package) با بقیهٔ اپ تا هیچ call site ای به import نیاز پیدا نکند.

// صف تایید ادمین: قرارداد قدیمی حفظ شده، اما پاسخ جدید conflict/capacity/audit را هم نمایش می‌دهد.

interface AdminClassApi {
    @GET("admin/pending_classes")
    suspend fun getPendingClasses(): List<PendingClassItem>

    @POST("admin/approve_class/{id}")
    suspend fun approveClass(@Path("id") id: Int): SimpleResponse

    @DELETE("admin/reject_class/{id}")
    suspend fun rejectClass(@Path("id") id: Int, @Query("reason") reason: String? = null): SimpleResponse
}
