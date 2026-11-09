package com.example.kharazmiadmin

import java.util.Calendar
import java.util.GregorianCalendar

/**
 * FIX H3-B1: Kotlin mirror of the server's central date converter
 * (Kharazmi_Server/today_summary.py: jalali_to_gregorian / parse_project_date).
 *
 * The app has NO existing converter: ir.hamsaa.persiandatepicker is only used as a
 * date-picker dialog for birth_date, so this self-contained port (same algorithm,
 * same year<1700 heuristic) keeps app and server logic identical with no new dependency.
 */
object JalaliUtils {

    private val DATE_RE = Regex("(?<!\\d)(\\d{4})[/-](\\d{1,2})[/-](\\d{1,2})(?!\\d)")
    private const val FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
    private const val AR_DIGITS = "٠١٢٣٤٥٦٧٨٩"

    private fun normalizeDigits(s: String): String {
        val sb = StringBuilder(s.length)
        for (c in s) {
            val fi = FA_DIGITS.indexOf(c)
            val ai = if (fi >= 0) -1 else AR_DIGITS.indexOf(c)
            sb.append(when {
                fi >= 0 -> '0' + fi
                ai >= 0 -> '0' + ai
                else -> c
            })
        }
        return sb.toString()
    }

    /** Exact port of server jalali_to_gregorian(); returns a Gregorian Calendar. */
    fun jalaliToGregorian(jyIn: Int, jm: Int, jd: Int): Calendar {
        require(jm in 1..12 && jd in 1..31) { "Invalid Jalali date" }
        val jy = jyIn + 1595
        var days = -355668 + (365 * jy) + ((jy / 33) * 8) + (((jy % 33) + 3) / 4) + jd
        days += if (jm < 7) (jm - 1) * 31 else ((jm - 7) * 30) + 186

        var gy = 400 * (days / 146097)
        days %= 146097
        if (days > 36524) {
            days -= 1
            gy += 100 * (days / 36524)
            days %= 36524
            if (days >= 365) days += 1
        }
        gy += 4 * (days / 1461)
        days %= 1461
        if (days > 365) {
            gy += (days - 1) / 365
            days = (days - 1) % 365
        }
        var gd = days + 1
        val monthDays = intArrayOf(0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
        if ((gy % 4 == 0 && gy % 100 != 0) || gy % 400 == 0) monthDays[2] = 29
        var gm = 1
        while (gm <= 12 && gd > monthDays[gm]) {
            gd -= monthDays[gm]
            gm += 1
        }
        return GregorianCalendar(gy, gm - 1, gd)
    }

    /**
     * Mirror of server parse_project_date(): parses a stored yyyy/MM/dd (or yyyy-MM-dd)
     * string that may be Jalali OR Gregorian. Same heuristic: year < 1700 => Jalali.
     * Tolerates non-zero-padded month/day (e.g. InvoiceActivity's old "1405/9/10").
     * Returns null on garbage (never throws).
     */
    fun parseProjectDate(value: String?): Calendar? {
        if (value.isNullOrBlank()) return null
        val m = DATE_RE.find(normalizeDigits(value)) ?: return null
        val (y, mo, d) = m.destructured
        return try {
            val year = y.toInt()
            val month = mo.toInt()
            val day = d.toInt()
            if (year < 1700) {
                jalaliToGregorian(year, month, day)
            } else {
                GregorianCalendar(year, month - 1, day).apply {
                    isLenient = false
                    time // force validation; throws on impossible dates
                }
            }
        } catch (e: Exception) {
            null
        }
    }

    private fun atMidnight(c: Calendar): Calendar = (c.clone() as Calendar).apply {
        set(Calendar.HOUR_OF_DAY, 0)
        set(Calendar.MINUTE, 0)
        set(Calendar.SECOND, 0)
        set(Calendar.MILLISECOND, 0)
    }

    /**
     * True if the stored due string is strictly before Gregorian today.
     * Null/garbage => false (shown as «در انتظار», never crashes).
     */
    fun isBeforeToday(value: String?): Boolean {
        val due = parseProjectDate(value) ?: return false
        return atMidnight(due).before(atMidnight(GregorianCalendar.getInstance()))
    }

    // ---- FIX H3-B2: Gregorian→Jalali direction (exact port of server gregorian_to_jalali) ----

    /** Exact port of server gregorian_to_jalali(); months are 1-based. */
    fun gregorianToJalali(gy: Int, gm: Int, gd: Int): Triple<Int, Int, Int> {
        val cumulativeMonthDays = intArrayOf(0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334)
        val adjustedYear = if (gm > 2) gy + 1 else gy
        var days = (355666
            + (365 * gy)
            + ((adjustedYear + 3) / 4)
            - ((adjustedYear + 99) / 100)
            + ((adjustedYear + 399) / 400)
            + gd
            + cumulativeMonthDays[gm - 1])

        var jy = -1595 + (33 * (days / 12053))
        days %= 12053
        jy += 4 * (days / 1461)
        days %= 1461
        if (days > 365) {
            jy += (days - 1) / 365
            days = (days - 1) % 365
        }

        val jm: Int
        val jd: Int
        if (days < 186) {
            jm = 1 + (days / 31)
            jd = 1 + (days % 31)
        } else {
            jm = 7 + ((days - 186) / 30)
            jd = 1 + ((days - 186) % 30)
        }
        return Triple(jy, jm, jd)
    }

    /** Zero-padded Jalali string, always with Latin digits (server-safe). */
    fun formatJalali(jy: Int, jm: Int, jd: Int): String =
        String.format(java.util.Locale.US, "%04d/%02d/%02d", jy, jm, jd)

    /** Today's date as a real Jalali string (replaces the year-621 approximation). */
    fun todayJalaliString(): String {
        val cal = GregorianCalendar.getInstance()
        val (jy, jm, jd) = gregorianToJalali(
            cal.get(Calendar.YEAR), cal.get(Calendar.MONTH) + 1, cal.get(Calendar.DAY_OF_MONTH)
        )
        return formatJalali(jy, jm, jd)
    }

    /** (Today + daysAhead) as a real Jalali string. */
    fun jalaliStringDaysFromNow(daysAhead: Int): String {
        val cal = GregorianCalendar.getInstance()
        cal.add(Calendar.DAY_OF_YEAR, daysAhead)
        val (jy, jm, jd) = gregorianToJalali(
            cal.get(Calendar.YEAR), cal.get(Calendar.MONTH) + 1, cal.get(Calendar.DAY_OF_MONTH)
        )
        return formatJalali(jy, jm, jd)
    }

    /**
     * FIX (تاریخچهٔ جلسات): نام روز هفته برای یک تاریخ ذخیره‌شده (شمسی یا میلادی).
     *
     * منبع اصلی این نام سرور است (فیلد `weekday` در پاسخ)؛ این تابع فقط fallback برای پاسخ/کش
     * قدیمی است که آن فیلد را ندارد. روزِ هفته به تقویم وابسته نیست (یک لحظهٔ زمانی واحد است)،
     * پس همان Calendar میلادی برای تاریخ شمسی هم درست جواب می‌دهد. نامعتبر ⇒ "".
     */
    fun persianWeekdayName(value: String?): String {
        val cal = parseProjectDate(value) ?: return ""
        return when (cal.get(Calendar.DAY_OF_WEEK)) {
            Calendar.SATURDAY -> "شنبه"
            Calendar.SUNDAY -> "یکشنبه"
            Calendar.MONDAY -> "دوشنبه"
            Calendar.TUESDAY -> "سه‌شنبه"
            Calendar.WEDNESDAY -> "چهارشنبه"
            Calendar.THURSDAY -> "پنجشنبه"
            Calendar.FRIDAY -> "جمعه"
            else -> ""
        }
    }

    /** (Today - daysAgo) as a real Jalali string. */
    fun jalaliStringDaysAgo(daysAgo: Int): String {
        val cal = GregorianCalendar.getInstance()
        cal.add(Calendar.DAY_OF_YEAR, -daysAgo)
        val (jy, jm, jd) = gregorianToJalali(
            cal.get(Calendar.YEAR), cal.get(Calendar.MONTH) + 1, cal.get(Calendar.DAY_OF_MONTH)
        )
        return formatJalali(jy, jm, jd)
    }
}
