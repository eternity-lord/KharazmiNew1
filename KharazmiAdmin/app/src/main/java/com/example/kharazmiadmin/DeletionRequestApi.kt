package com.example.kharazmiadmin

import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

// لایهٔ دادهٔ DeletionRequestApi: قراردادِ Retrofit این دامنه؛ از DeletionRequestsActivity.kt بیرون کشیده شد (فاز P4d).
// هم‌بسته (same package) با بقیهٔ اپ تا هیچ call site ای به import نیاز پیدا نکند.

// API

interface DeletionRequestApi {
    @GET("classes/deletion_requests")
    suspend fun getRequests(@Query("status") status: String? = null): List<DeletionRequestItem>

    @POST("classes/deletion_requests/{id}/approve")
    suspend fun approve(@Path("id") id: Int): SimpleResponse

    @POST("classes/deletion_requests/{id}/reject")
    suspend fun reject(@Path("id") id: Int, @Body req: DeletionRejectRequest): SimpleResponse
}
