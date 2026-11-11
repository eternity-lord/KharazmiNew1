package com.example.kharazmiadmin

import retrofit2.http.GET
import retrofit2.http.Query

// لایهٔ دادهٔ DebtorsApi: قراردادِ Retrofit این دامنه؛ از DebtorsActivity.kt بیرون کشیده شد (فاز P4d).
// هم‌بسته (same package) با بقیهٔ اپ تا هیچ call site ای به import نیاز پیدا نکند.

interface DebtorsApi {
    @GET("finance/reports/debtors_grouped")
    suspend fun getGrouped(@Query("search") search: String? = null): DebtorsGroupedResponse
}
