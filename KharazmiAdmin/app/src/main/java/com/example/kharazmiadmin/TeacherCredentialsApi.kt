package com.example.kharazmiadmin

import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Path
import retrofit2.http.Query

// لایهٔ دادهٔ TeacherCredentialsApi: قراردادِ Retrofit این دامنه؛ از TeacherCredentialsActivity.kt بیرون کشیده شد (فاز P4d).
// هم‌بسته (same package) با بقیهٔ اپ تا هیچ call site ای به import نیاز پیدا نکند.

interface TeacherCredentialsApi {
    @GET("admin/teachers/search")
    suspend fun searchTeachers(@Query("query") q: String?): List<PersonListItem>

    @GET("admin/teachers/{id}/credentials")
    suspend fun getCredentials(@Path("id") id: Int): TeacherCredentialsResponse

    @POST("admin/teachers/{id}/credentials/reset_password")
    suspend fun resetPassword(@Path("id") id: Int): ResetPasswordResponse

    @PUT("admin/teachers/{id}/credentials")
    suspend fun updateCredentials(@Path("id") id: Int, @Body req: TeacherCredentialsUpdateRequest): SimpleResponse
}
