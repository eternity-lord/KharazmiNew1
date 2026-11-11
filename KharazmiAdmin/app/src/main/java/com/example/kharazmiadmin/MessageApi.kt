package com.example.kharazmiadmin

import retrofit2.http.*

// لایهٔ دادهٔ MessageApi: قراردادِ Retrofit این دامنه؛ از MessageActivity.kt بیرون کشیده شد (فاز P4d).
// هم‌بسته (same package) با بقیهٔ اپ تا هیچ call site ای به import نیاز پیدا نکند.

interface MessageApi {
    @GET("messages/conversations")
    suspend fun getConversations(): List<ConversationItem>

    @POST("messages/conversations/create")
    suspend fun createConversation(@Body req: ConversationCreateRequest): SimpleResponse

    @GET("messages/conversations/{id}/history")
    suspend fun getHistory(@Path("id") id: Int): List<MessageHistoryItem>

    @POST("messages/conversations/{id}/send")
    suspend fun sendMessage(@Path("id") id: Int, @Body req: MessageSendRequest): SimpleResponse

    @POST("messages/broadcast")
    suspend fun sendBroadcast(@Body req: BroadcastMessageRequest): SimpleResponse

    @POST("messages/conversations/{id}/pin")
    suspend fun setPin(@Path("id") id: Int, @Body req: PinToggleRequest): PinToggleResponse
}
