package com.example.kharazmiadmin

import retrofit2.http.GET
import retrofit2.http.Query

// لایهٔ دادهٔ AdminListApi: قراردادِ Retrofit این دامنه؛ از PersonListActivity.kt بیرون کشیده شد (فاز P4d).
// هم‌بسته (same package) با بقیهٔ اپ تا هیچ call site ای به import نیاز پیدا نکند.

interface AdminListApi {
    @GET("admin/students/search")
    suspend fun getStudents(@Query("query") q: String?): List<PersonListItem>

    @GET("admin/teachers/search")
    suspend fun getTeachers(@Query("query") q: String?): List<PersonListItem>
}
