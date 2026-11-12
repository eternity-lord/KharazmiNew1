package com.example.kharazmiadmin

import java.util.Locale
import kotlin.math.abs

/**
 * قالب‌بندی و نرمال‌سازیِ ورودیِ صفحهٔ پروفایل دانش‌آموز — از `StudentProfileActivity`
 * بیرون کشیده شد (فاز P4d، برش ۳).
 *
 * هر سه تابع خالص‌اند: نه Context می‌گیرند نه View، پس بدونِ Activity قابلِ تست‌اند.
 * بدنه‌ها کلمه‌به‌کلمه از Activity منتقل شده‌اند و تنها تغییر، برداشتنِ `private` است
 * چون عضوِ یک `object` شده‌اند. `isValidJalaliDate` همچنان خواهرِ خودش
 * (`normalizePersianDigits`) را بدونِ prefix صدا می‌زند.
 */
object StudentProfileFormat {

    fun formatCurrency(value: Long): String =
        String.format(Locale("en", "US"), "%,d", abs(value))

    fun normalizePersianDigits(input: String): String {
        val fa = "۰۱۲۳۴۵۶۷۸۹"
        val ar = "٠١٢٣٤٥٦٧٨٩"
        val sb = StringBuilder(input.length)
        for (c in input) {
            val fi = fa.indexOf(c)
            val ai = if (fi >= 0) -1 else ar.indexOf(c)
            sb.append(when {
                fi >= 0 -> ('0' + fi)
                ai >= 0 -> ('0' + ai)
                else -> c
            })
        }
        return sb.toString()
    }

    fun isValidJalaliDate(raw: String): Boolean {
        val normalized = normalizePersianDigits(raw.trim())
        val re = Regex("^\\d{4}/\\d{2}/\\d{2}$")
        if (!re.matches(normalized)) return false
        return try {
            JalaliUtils.parseProjectDate(normalized) != null
        } catch (_: Exception) { false }
    }
}
