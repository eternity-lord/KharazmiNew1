package com.example.kharazmiadmin

import retrofit2.http.*

// لایهٔ دادهٔ CalendarApi: قراردادِ Retrofit این دامنه؛ از CalendarActivity.kt بیرون کشیده شد (فاز P4d).
// هم‌بسته (same package) با بقیهٔ اپ تا هیچ call site ای به import نیاز پیدا نکند.

interface CalendarApi {
    @POST("rooms/create")
    suspend fun createRoom(@Body req: RoomCreateRequest): RoomItem

    @GET("rooms/list")
    suspend fun getRoomsList(): List<RoomItem>

    @POST("calendar/check_conflicts")
    suspend fun checkConflicts(@Body req: ConflictCheckRequest): ConflictCheckResponse

    @GET("calendar/events")
    suspend fun getCalendarEvents(): List<CalendarEventItem>
}
