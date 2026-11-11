package com.example.kharazmiadmin

import retrofit2.http.GET
import retrofit2.http.Path

// لایهٔ دادهٔ ReceiptDetailsApi: قراردادِ Retrofit این دامنه؛ از InvoiceActivity.kt بیرون کشیده شد (فاز P4d).
// هم‌بسته (same package) با بقیهٔ اپ تا هیچ call site ای به import نیاز پیدا نکند.

interface ReceiptDetailsApi {
    @GET("/finance/receipt/{transaction_id}")
    suspend fun getReceiptDetails(@Path("transaction_id") id: Long): ReceiptDetailsResponse
}
