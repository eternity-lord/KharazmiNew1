package com.example.kharazmiadmin

import retrofit2.http.GET
import retrofit2.http.Query

// لایهٔ دادهٔ ParentContactsApi: قراردادِ Retrofit این دامنه؛ از ParentContactsActivity.kt بیرون کشیده شد (فاز P4d).
// هم‌بسته (same package) با بقیهٔ اپ تا هیچ call site ای به import نیاز پیدا نکند.

interface ParentContactsApi {
    @GET("admin/parent_contacts")
    suspend fun getParentContacts(
        @Query("class_id") classId: Int?,
        @Query("search") search: String?
    ): List<ParentContactItem>
}
