package com.example.kharazmiadmin

/**
 * بیرون کشیدنِ پیامِ خطای سرور از پاسخِ Retrofit — از `StudentProfileActivity` بیرون
 * کشیده شد (فاز P4d، برش ۳).
 *
 * ترتیبِ اولویت دست‌نخورده مانده: نخست `detail` (میدانِ استانداردِ FastAPI) و اگر خالی
 * بود `message`؛ در هر خطای دیگر یا پاسخِ غیرِ HTTP مقدارِ `null` برمی‌گردد تا فراخوان
 * بتواند مثلِ قبل به `e.message` و سپس رشتهٔ `common_unknown_error` برگردد.
 */
object StudentProfileErrors {

    fun extractServerDetail(e: Exception): String? {
        return try {
            if (e is retrofit2.HttpException) {
                val body = e.response()?.errorBody()?.string()
                if (!body.isNullOrBlank()) {
                    val obj = org.json.JSONObject(body)
                    val d = obj.optString("detail", "")
                    if (d.isNotBlank()) d else obj.optString("message", null)?.takeIf { it.isNotBlank() }
                } else null
            } else null
        } catch (_: Exception) { null }
    }
}
