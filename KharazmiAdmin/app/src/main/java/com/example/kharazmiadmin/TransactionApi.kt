package com.example.kharazmiadmin

import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.PUT
import retrofit2.http.Path
import retrofit2.http.Query

// لایهٔ دادهٔ TransactionApi: قراردادِ Retrofit این دامنه؛ از TransactionManageActivity.kt بیرون کشیده شد (فاز P4d).
// هم‌بسته (same package) با بقیهٔ اپ تا هیچ call site ای به import نیاز پیدا نکند.

// 1. تعریف API داخلی همین صفحه

interface TransactionApi {
    @GET("admin/transactions/list")
    suspend fun getTransactions(@Query("search") search: String?): List<TransactionFullItem>

    @DELETE("admin/transactions/{id}")
    suspend fun deleteTransaction(@Path("id") id: Int): SimpleResponse

    @PUT("admin/transactions/{id}")
    suspend fun updateTransaction(@Path("id") id: Int, @Body data: TransactionUpdateData): SimpleResponse
}
