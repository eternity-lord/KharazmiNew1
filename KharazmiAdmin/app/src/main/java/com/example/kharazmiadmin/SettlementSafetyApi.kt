package com.example.kharazmiadmin

import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Body
import retrofit2.http.Query
import retrofit2.http.Path

// لایهٔ دادهٔ SettlementSafetyApi: قراردادِ Retrofit این دامنه؛ از TeacherProfileActivity.kt بیرون کشیده شد (فاز P4d).
// هم‌بسته (same package) با بقیهٔ اپ تا هیچ call site ای به import نیاز پیدا نکند.

interface SettlementSafetyApi {
    @POST("teachers/{teacher_id}/settlements/{settlement_id}/reverse")
    suspend fun reverseSettlement(@Path("teacher_id") teacherId: Int, @Path("settlement_id") settlementId: Int, @Query("reason") reason: String): SimpleResponse
    @PUT("teachers/{teacher_id}/settlements/{settlement_id}/edit")
    suspend fun editSettlement(@Path("teacher_id") teacherId: Int, @Path("settlement_id") settlementId: Int, @Body request: SettlementEditRequest): SimpleResponse
}
