package com.example.kharazmiadmin

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.Calendar

/**
 * FIX(P4d-5): `JalaliUtils.jalaliToGregorian` **پورتِ ناقصِ** سرور بود.
 *
 * سرور (`Kharazmi_Server/today_summary.py::jalali_to_gregorian`) بعدِ تبدیل یک گاردِ
 * رفت‌وبرگشتی دارد:
 *
 *     result = datetime.date(gy, gm, gd)
 *     if gregorian_to_jalali(result) != original:
 *         raise ValueError("Invalid Jalali date")
 *
 * ولی پورتِ Kotlin با اینکه کامنتش می‌گفت «Exact port of server» آن گارد را نداشت؛
 * فقط `require(jm in 1..12 && jd in 1..31)` را می‌سنجید و بعد حلقهٔ
 * `while (gd > monthDays[gm])` روزِ اضافی را بی‌صدا به ماهِ بعد سُرسره می‌کرد.
 * نتیجه: تاریخِ **محال** به‌جایِ رد شدن، به تاریخِ دیگری تبدیل می‌شد —
 * `۱۴۰۴/۰۷/۳۱` (مهر ۳۰ روزه است) می‌شد `۲۰۲۵-۱۰-۲۳`، در حالی که سرور ردش می‌کند.
 *
 * این فقط یک تفاوتِ تئوری نبود: رویِ شبکهٔ کاملِ ورودی‌هایِ قابلِ رسیدن
 * (jy 1000..1699 × jm 1..12 × jd 1..31 = ۲۶۰٬۴۰۰ حالت) با اجرایِ تابعِ **واقعیِ**
 * سرور مقایسه شد ⇒ **۴٬۷۳۱ واگرایی** پیش ازِ گارد و **۰** پس از آن.
 *
 * شعاعِ اثر در برنامه: `parseProjectDate` (خواندنِ تاریخِ ذخیره‌شده) ←
 * `isBeforeToday` ← `StudentProfileActivity.kt:1067` یعنی پرچمِ «سررسیدِ گذشته»ی قسط.
 * و `isValidJalaliDate` (که در PR #18 درست شد) فقط **قالب** را می‌سنجد، پس
 * `۱۴۰۴/۰۷/۳۱` از آن گیت رد می‌شود و تا اینجا می‌آمد.
 *
 * هر مقدارِ انتظاریِ این تست پیش ازِ نوشتن، با اجرایِ همان تابعِ سرور در Python
 * راستی‌آزمایی شد (نه از حدسِ نویسنده): ۹ تاریخِ معتبر و ۸ تاریخِ مردود.
 */
class JalaliUtilsTest {

    /** نتیجهٔ تبدیل به «yyyy-MM-dd» — با Locale.US تا به زبانِ ماشینِ اجرا وابسته نباشد. */
    private fun gregorian(jy: Int, jm: Int, jd: Int): String {
        val c = JalaliUtils.jalaliToGregorian(jy, jm, jd)
        return String.format(
            java.util.Locale.US, "%04d-%02d-%02d",
            c.get(Calendar.YEAR), c.get(Calendar.MONTH) + 1, c.get(Calendar.DAY_OF_MONTH)
        )
    }

    /** `require` در Kotlin همان `IllegalArgumentException` است — هم‌نوع با `ValueError` سرور. */
    private fun rejects(jy: Int, jm: Int, jd: Int, why: String) {
        val e = assertThrows(
            "$jy/$jm/$jd باید رد شود ($why) — سرور هم ردش می‌کند",
            IllegalArgumentException::class.java
        ) { JalaliUtils.jalaliToGregorian(jy, jm, jd) }
        assertEquals("Invalid Jalali date", e.message)
    }

    // ── همان واگرایی‌هایی که با سرور اندازه‌گیری شدند ──

    @Test fun rejectsThe31stInThirtyDayMonths() {
        // مهر تا بهمن ۳۰ روزه‌اند؛ روزِ ۳۱ پیش‌تر بی‌صدا به ماهِ بعد می‌رفت
        rejects(1404, 7, 31, "مهر ۳۰ روز دارد")
        rejects(1404, 8, 31, "آبان ۳۰ روز دارد")
        rejects(1404, 9, 31, "آذر ۳۰ روز دارد")
        rejects(1404, 10, 31, "دی ۳۰ روز دارد")
        rejects(1404, 11, 31, "بهمن ۳۰ روز دارد")
    }

    @Test fun esfandIsRejectedOnDay30OnlyWhenTheYearIsNotLeap() {
        // این ظریف‌ترین حالت است: اعتبارِ اسفندِ ۳۰ به کبیسه‌بودنِ سال وابسته است و
        // هیچ range-check ساده‌ای نمی‌تواند بگیردش — فقط گاردِ رفت‌وبرگشتی می‌گیرد.
        assertEquals("2025-03-20", gregorian(1403, 12, 30)) // ۱۴۰۳ کبیسه است ⇒ معتبر
        rejects(1404, 12, 30, "۱۴۰۴ کبیسه نیست، اسفند ۲۹ روز دارد")
        rejects(1404, 12, 31, "اسفند هیچ‌وقت ۳۱ روز ندارد")
        rejects(1403, 12, 31, "اسفند هیچ‌وقت ۳۱ روز ندارد، حتی در کبیسه")
    }

    @Test fun rangeGuardStillRejectsImpossibleMonthAndDay() {
        // این‌ها را `require` از پیش می‌گرفت؛ قفل می‌شوند تا بازگشتِ ناخواستهٔ گاردِ
        // رفت‌وبرگشتی باعثِ از دست رفتنشان نشود.
        rejects(1404, 13, 1, "ماه ۱۳ وجود ندارد")
        rejects(1404, 0, 10, "ماه ۰ وجود ندارد")
        rejects(1404, 6, 32, "روز ۳۲ وجود ندارد")
        rejects(1404, 7, 0, "روز ۰ وجود ندارد")
    }

    // ── آنچه باید سالم بماند (جلوگیری از اصلاحِ بیش‌از‌حد) ──

    @Test fun convertsValidDatesExactlyLikeTheServer() {
        assertEquals("2025-10-22", gregorian(1404, 7, 30)) // آخرین روزِ معتبرِ مهر
        assertEquals("2026-03-21", gregorian(1405, 1, 1))  // نوروز ۱۴۰۵
        assertEquals("2026-03-20", gregorian(1404, 12, 29)) // آخرین روزِ سالِ غیرِکبیسه
        assertEquals("2026-02-19", gregorian(1404, 11, 30))
        assertEquals("2025-12-21", gregorian(1404, 9, 30))
        assertEquals("2026-12-01", gregorian(1405, 9, 10))
    }

    @Test fun firstSixMonthsStillAcceptDay31() {
        // فروردین تا شهریور ۳۱ روزه‌اند — گاردِ تازه نباید این‌ها را رد کند
        assertEquals("2025-04-20", gregorian(1404, 1, 31))
        assertEquals("2025-09-22", gregorian(1404, 6, 31))
        for (jm in 1..6) {
            assertTrue(
                "۱۴۰۴/$jm/۳۱ باید معتبر بماند",
                runCatching { JalaliUtils.jalaliToGregorian(1404, jm, 31) }.isSuccess
            )
        }
    }

    @Test fun everyAcceptedDateRoundTripsBackToItself() {
        // خاصیتِ اصلیِ گارد: هر تاریخی که پذیرفته می‌شود باید با برگشتِ دوطرفه همان شود.
        // ۴۱ سال × ۱۲ ماه × ۳۱ روز = ۱۵٬۲۵۲ ورودی؛ مردودها skip می‌شوند.
        var checked = 0
        for (jy in 1380..1420) {
            for (jm in 1..12) {
                for (jd in 1..31) {
                    val cal = try {
                        JalaliUtils.jalaliToGregorian(jy, jm, jd)
                    } catch (e: IllegalArgumentException) {
                        continue
                    }
                    val back = JalaliUtils.gregorianToJalali(
                        cal.get(Calendar.YEAR),
                        cal.get(Calendar.MONTH) + 1,
                        cal.get(Calendar.DAY_OF_MONTH)
                    )
                    assertEquals(
                        "$jy/$jm/$jd رفت‌وبرگشت نکرد",
                        Triple(jy, jm, jd), back
                    )
                    checked++
                }
            }
        }
        assertTrue("باید دستِ‌کم ۱۴٬۰۰۰ تاریخِ معتبر سنجیده شود، نه $checked", checked > 14_000)
    }

    // ── تأثیر رویِ لایهٔ پارسر و مصرف‌کنندهٔ واقعی‌اش ──

    @Test fun parseProjectDateReturnsNullInsteadOfRollingImpossibleDatesForward() {
        // قراردادِ parseProjectDate «رویِ garbage مقدارِ null و هرگز throw» است؛ پیش ازِ
        // این گارد، تاریخِ محال نه null می‌شد نه throw — یک تاریخِ **غلط** می‌داد.
        assertNull(JalaliUtils.parseProjectDate("1404/07/31"))
        assertNull(JalaliUtils.parseProjectDate("1404-11-31"))
        assertNull(JalaliUtils.parseProjectDate("1404/12/30"))
        assertNull(JalaliUtils.parseProjectDate("1404/13/01"))
        assertNull(JalaliUtils.parseProjectDate("not-a-date"))
        assertNull(JalaliUtils.parseProjectDate(""))
        assertNull(JalaliUtils.parseProjectDate(null))
    }

    @Test fun jalaliAndGregorianBranchesNowAgreeOnImpossibleDates() {
        // شاخهٔ میلادی از پیش با isLenient=false سخت‌گیر بود؛ شاخهٔ جلالی نبود.
        // این تست همان ناسازگاریِ درونیِ یک تابع را قفل می‌کند.
        assertNull(JalaliUtils.parseProjectDate("1404/07/31")) // شاخهٔ جلالی (سال < ۱۷۰۰)
        assertNull(JalaliUtils.parseProjectDate("2025/02/30")) // شاخهٔ میلادی (سال ≥ ۱۷۰۰)
        // و هر دو شاخه تاریخِ معتبرِ خودشان را می‌پذیرند
        assertEquals(2025, JalaliUtils.parseProjectDate("1404/07/30")!!.get(Calendar.YEAR))
        assertEquals(2025, JalaliUtils.parseProjectDate("2025-10-22")!!.get(Calendar.YEAR))
    }

    @Test fun parseProjectDateStillToleratesUnpaddedAndDashSeparatedStoredData() {
        val unpadded = JalaliUtils.parseProjectDate("1405/9/10")
        val padded = JalaliUtils.parseProjectDate("1405/09/10")
        assertTrue("قالبِ بدونِ صفرِ پیشرو باید پذیرفته شود (دادهٔ ذخیره‌شدهٔ قدیمی)", unpadded != null)
        assertTrue(padded != null)
        assertEquals(
            unpadded!!.get(Calendar.DAY_OF_YEAR),
            padded!!.get(Calendar.DAY_OF_YEAR)
        )
    }

    @Test fun isBeforeTodayIsFalseForGarbageAndImpossibleDates() {
        // مصرف‌کنندهٔ واقعی: StudentProfileActivity.kt:1067 (پرچمِ «سررسیدِ گذشته»).
        // garbage ⇒ false یعنی «در انتظار»، هرگز کرش و هرگز برچسبِ اشتباه.
        assertFalse(JalaliUtils.isBeforeToday(null))
        assertFalse(JalaliUtils.isBeforeToday(""))
        assertFalse(JalaliUtils.isBeforeToday("not-a-date"))
        assertFalse(JalaliUtils.isBeforeToday("1404/07/31"))
    }

    @Test fun isBeforeTodayStaysIndependentOfTheRunDate() {
        // با تاریخ‌هایی که خودِ JalaliUtils می‌سازد نوشته شده، پس فردا هم سبز می‌ماند.
        assertTrue(
            "۳۶۵ روز پیش باید گذشته باشد",
            JalaliUtils.isBeforeToday(JalaliUtils.jalaliStringDaysAgo(365))
        )
        assertTrue(
            "دیروز باید گذشته باشد",
            JalaliUtils.isBeforeToday(JalaliUtils.jalaliStringDaysAgo(1))
        )
        assertFalse(
            "فردا نباید گذشته باشد",
            JalaliUtils.isBeforeToday(JalaliUtils.jalaliStringDaysFromNow(1))
        )
        assertFalse(
            "۹۰ روز بعد نباید گذشته باشد",
            JalaliUtils.isBeforeToday(JalaliUtils.jalaliStringDaysFromNow(90))
        )
    }

    @Test fun datesTheAppGeneratesAreAlwaysAcceptedByTheNewGuard() {
        // مهم‌ترین خاصیتِ عملی: گاردِ تازه نباید چیزی را که خودِ برنامه تولید می‌کند
        // رد کند (دامی که در PR #18 با isValidJalaliDate دیده شد).
        val samples = listOf(
            JalaliUtils.todayJalaliString(),
            JalaliUtils.jalaliStringDaysFromNow(1),
            JalaliUtils.jalaliStringDaysFromNow(365),
            JalaliUtils.jalaliStringDaysAgo(1),
            JalaliUtils.jalaliStringDaysAgo(365)
        )
        for (s in samples) {
            val cal = JalaliUtils.parseProjectDate(s)
            assertTrue("تاریخِ تولیدیِ خودِ برنامه رد شد: $s", cal != null)
        }
    }
}
