package com.example.kharazmiadmin

import retrofit2.http.GET
import retrofit2.http.Query

// لایهٔ دادهٔ ChartApi: قراردادِ Retrofit این دامنه؛ از ChartActivity.kt بیرون کشیده شد (فاز P4d).
// هم‌بسته (same package) با بقیهٔ اپ تا هیچ call site ای به import نیاز پیدا نکند.

interface ChartApi {
    @GET("reports/chart-data")
    suspend fun getChartData(
        @Query("class_id") classId: Int?,
        @Query("start_date") startDate: String?,
        @Query("end_date") endDate: String?
    ): ChartDataResponse

    @GET("analytics/enrollment_funnel")
    suspend fun getEnrollmentFunnel(
        @Query("start_date") startDate: String,
        @Query("end_date") endDate: String,
        @Query("branch_id") branchId: Int
    ): EnrollmentFunnelResponse
}
