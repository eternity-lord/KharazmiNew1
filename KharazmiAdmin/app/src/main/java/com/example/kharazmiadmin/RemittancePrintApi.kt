package com.example.kharazmiadmin

import retrofit2.http.Body
import retrofit2.http.POST

// لایهٔ دادهٔ RemittancePrintApi: قراردادِ Retrofit این دامنه؛ از InvoiceActivity.kt بیرون کشیده شد (فاز P4d).
// هم‌بسته (same package) با بقیهٔ اپ تا هیچ call site ای به import نیاز پیدا نکند.

// Remittance Print API Interface

interface RemittancePrintApi {
    @POST("/finance/receipt/print")
    suspend fun printReceipt(@Body req: PrintReceiptRequest): PrintReceiptResponse

    @POST("/finance/receipt/pdf")
    suspend fun generatePdfReceipt(@Body req: PrintReceiptRequest): PdfReceiptResponse
}
