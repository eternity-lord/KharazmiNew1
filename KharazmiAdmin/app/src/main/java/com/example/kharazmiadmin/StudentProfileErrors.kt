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
                    // FIX(kotlin-warning): دومین آرگومانِ optString پیش‌تر null بود، ولی امضایِ Java آن
                    // پارامتر را String (نه String?) اعلام کرده است؛ همان یک null تنها هشدارِ
                    // «Java type mismatch» در کلِ پروژه را می‌ساخت. رفتار هیچ تغییری نکرده است: این
                    // fallback تنها وقتی خوانده می‌شود که کلید غایب باشد؛ در آن حالت پیش‌تر هم نتیجه
                    // null بود (فراخوانِ امن رویِ null) و اکنون رشتهٔ خالی در isNotBlank رد می‌شود و
                    // باز null. خطِ بالایی هم برایِ «detail» از قبل رشتهٔ خالی را می‌داد.
                    if (d.isNotBlank()) d else obj.optString("message", "").takeIf { it.isNotBlank() }
                } else null
            } else null
        } catch (_: Exception) { null }
    }
}
