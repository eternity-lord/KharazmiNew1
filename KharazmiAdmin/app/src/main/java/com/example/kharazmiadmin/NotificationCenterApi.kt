package com.example.kharazmiadmin

import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path

// لایهٔ دادهٔ NotificationCenterApi: قراردادِ Retrofit این دامنه؛ از NotificationCenterActivity.kt بیرون کشیده شد (فاز P4d).
// هم‌بسته (same package) با بقیهٔ اپ تا هیچ call site ای به import نیاز پیدا نکند.

interface NotificationCenterApi {
    @GET("notifications")
    suspend fun getNotifications(): List<NotificationItem>

    // FIX(admin-notifications): endpoint شمارش خوانده‌نشده‌ها (قبلاً وجود نداشت)
    @GET("notifications/unread_count")
    suspend fun getUnreadCount(): UnreadCountResponse

    @POST("notifications/{id}/read")
    suspend fun markRead(@Path("id") id: Int): SimpleResponse

    @POST("notifications/read_all")
    suspend fun markAllRead(): SimpleResponse
}
