package com.example.kharazmiadmin

import android.content.Context

/**
 * فیلترهای درخواستِ ممیزی مالی — یک شیءِ دادهٔ خالص.
 *
 * پیش از این، هر دو نقطهٔ فراخوانی (صفحه‌بندی و خروجی CSV) همان هشت آرگومانِ نام‌دار را
 * دستی و جداگانه می‌ساختند؛ یک شیءِ مشترک یعنی دیگر نمی‌توانند ناخواسته از هم واگرا شوند.
 * `userId` عمداً اینجا نیست: صفحه هرگز بر اساسِ کاربر فیلتر نمی‌کند (مثلِ قبل null می‌ماند).
 */
data class AuditTrailFilter(
    val entityType: String?,
    val entityId: Int?,
    val action: String?,
    val startDate: String?,
    val endDate: String?,
    val search: String?
)

/**
 * لایهٔ دادهٔ ممیزی مالی — از `AuditTrailActivity` بیرون کشیده شد (فاز P4d، برش ۲).
 *
 * فقط `GET /audit-trail/logs` مصرف می‌شود؛ هیچ endpoint جدیدی لازم نشد و سرور
 * دست‌نخورده است. هیچ View، Context یا coroutine-scope ای در این کلاس نگه داشته نمی‌شود
 * (به‌جزِ ساختِ یک‌بارهٔ Retrofit در `from`)، پس تستِ واحدش به Activity نیاز ندارد.
 */
class AuditTrailRepository(private val api: AuditTrailApi) {

    /** یک صفحه از لاگ‌ها با همان فیلترها (دقیقاً همان کوئریِ قبلی). */
    suspend fun fetchPage(filter: AuditTrailFilter, page: Int, limit: Int): AuditTrailResponse =
        api.getLogs(
            entityType = filter.entityType,
            entityId = filter.entityId,
            action = filter.action,
            startDate = filter.startDate,
            endDate = filter.endDate,
            search = filter.search,
            page = page,
            limit = limit
        )

    /**
     * جمع‌آوریِ چند صفحه برای خروجی CSV. حلقهٔ `while` عیناً از Activity منتقل شده:
     * تا وقتی صفحهٔ بعدی هست و از `maxPages` نگذشته، ادامه می‌دهد.
     */
    suspend fun collectForExport(filter: AuditTrailFilter, limit: Int, maxPages: Int): List<AuditTrailLog> {
        val collected = mutableListOf<AuditTrailLog>()
        var page = 1
        var pages = 1
        while (page <= pages && page <= maxPages) {
            val response = fetchPage(filter, page, limit)
            collected.addAll(response.logs)
            pages = response.pages
            page += 1
        }
        return collected
    }

    companion object {
        /** تنها نقطهٔ ساختِ Retrofit برای این دامنه (قبلاً داخلِ `setupApi` در Activity بود). */
        fun from(context: Context): AuditTrailRepository =
            AuditTrailRepository(RetrofitClient.getInstance(context).create(AuditTrailApi::class.java))
    }
}
