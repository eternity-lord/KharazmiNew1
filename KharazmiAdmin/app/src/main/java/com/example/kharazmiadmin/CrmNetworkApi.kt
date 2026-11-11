package com.example.kharazmiadmin

import retrofit2.http.*

// لایهٔ دادهٔ CrmNetworkApi: قراردادِ Retrofit این دامنه؛ از CrmLeadsActivity.kt بیرون کشیده شد (فاز P4d).
// هم‌بسته (same package) با بقیهٔ اپ تا هیچ call site ای به import نیاز پیدا نکند.

interface CrmNetworkApi {
    @POST("crm/leads/create")
    suspend fun createLead(@Body req: LeadCreateRequest): LeadResponseModel

    @GET("crm/leads/list")
    suspend fun getLeadsList(): List<LeadResponseModel>

    @POST("crm/leads/{id}/notes")
    suspend fun addNotes(@Path("id") id: Int, @Body req: LeadNoteRequest): SimpleResponse

    @POST("crm/leads/{id}/convert")
    suspend fun convertLead(@Path("id") id: Int): SimpleResponse
}
