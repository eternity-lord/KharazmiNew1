package com.example.kharazmiadmin

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * FIX: گاردِ تاریخِ سررسیدِ قسط همیشه `false` می‌داد.
 *
 * الگویِ regex در `StudentProfileFormat.isValidJalaliDate` یک سطح اضافه escape داشت
 * (`"\\\\d"` در منبع ⇒ `\\d` در زمانِ اجرا ⇒ «backslashِ واقعی سپس حرفِ d»), پس با هیچ
 * تاریخِ واقعی‌ای نمی‌خواند و `showCreateInstallmentDialog` هر ثبتِ قسطی را با
 * `installment_error_due` رد می‌کرد — حتی مقداری را که خودِ برنامه در همان فیلد
 * پیش‌پر می‌کند (`etDue.setText(JalaliUtils.todayJalaliString())`).
 *
 * نخستین تستِ همین فایل همان حالتِ از دست رفته را قفل می‌کند: هر چه `JalaliUtils`
 * به‌عنوانِ «امروز» می‌سازد باید برای گارد قابلِ قبول باشد. این تست مستقل از تاریخِ
 * اجراست، چون قالبِ `%04d/%02d/%02d` همیشه با الگو می‌خواند.
 *
 * قراردادِ قالب عمداً سخت‌گیرانه ماند: `JalaliUtils.formatJalali` همان قالبِ
 * «server-safe» با اسلش و صفر-پرشده است، پس جداکنندهٔ `-` و رقمِ تک‌رقمی رد می‌شوند.
 * (پارسرِ عمومیِ `JalaliUtils.parseProjectDate` هر دو را می‌پذیرد؛ اینجا بحثِ ورودیِ
 * کاربر است، نه خواندنِ دادهٔ ذخیره‌شده.)
 */
class StudentProfileFormatTest {

    // ── گاردِ تاریخ: همان مقداری که خودِ برنامه تولید می‌کند ──

    @Test fun acceptsTheDateTheAppPrefillsIntoTheDueField() {
        assertTrue(
            "todayJalaliString() باید همیشه از گارد بگذرد — این همان مقدارِ پیش‌فرضِ etDue است",
            StudentProfileFormat.isValidJalaliDate(JalaliUtils.todayJalaliString())
        )
    }

    @Test fun acceptsDatesTheAppGeneratesForTheFuture() {
        for (daysAhead in intArrayOf(1, 7, 30, 90, 365)) {
            assertTrue(
                "jalaliStringDaysFromNow($daysAhead) رد شد",
                StudentProfileFormat.isValidJalaliDate(JalaliUtils.jalaliStringDaysFromNow(daysAhead))
            )
        }
    }

    @Test fun acceptsCanonicalZeroPaddedJalaliDate() {
        assertTrue(StudentProfileFormat.isValidJalaliDate("1404/08/21"))
    }

    @Test fun acceptsPersianAndArabicDigitsAfterNormalization() {
        assertTrue(StudentProfileFormat.isValidJalaliDate("۱۴۰۴/۰۸/۲۱"))
        assertTrue(StudentProfileFormat.isValidJalaliDate("١٤٠٤/٠٨/٢١"))
    }

    @Test fun acceptsSurroundingWhitespace() {
        assertTrue(StudentProfileFormat.isValidJalaliDate("  1404/08/21  "))
    }

    // ── آنچه باید رد شود ──

    @Test fun rejectsTheLiteralBackslashPatternTheOldRegexActuallyMatched() {
        // پیش از رفع، این تنها رشته‌ای بود که گارد می‌پذیرفت — و هیچ کاربری هرگز نمی‌نوشتش.
        assertFalse(StudentProfileFormat.isValidJalaliDate("\\dddd/\\dd/\\dd"))
    }

    @Test fun rejectsHyphenSeparatorBecauseTheServerSafeFormUsesSlash() {
        assertFalse(StudentProfileFormat.isValidJalaliDate("1404-08-21"))
    }

    @Test fun rejectsNonZeroPaddedMonthAndDay() {
        assertFalse(StudentProfileFormat.isValidJalaliDate("1404/8/21"))
        assertFalse(StudentProfileFormat.isValidJalaliDate("1404/08/1"))
    }

    @Test fun rejectsImpossibleMonth() {
        // ماهِ ۱۳ وجود ندارد؛ `jalaliToGregorian` با require رد می‌کند و
        // `parseProjectDate` هیچ‌وقت throw نمی‌کند بلکه null می‌دهد.
        assertFalse(StudentProfileFormat.isValidJalaliDate("1404/13/01"))
        assertFalse(StudentProfileFormat.isValidJalaliDate("1404/00/01"))
    }

    @Test fun rejectsGarbageAndEmpty() {
        assertFalse(StudentProfileFormat.isValidJalaliDate(""))
        assertFalse(StudentProfileFormat.isValidJalaliDate("   "))
        assertFalse(StudentProfileFormat.isValidJalaliDate("not a date"))
        assertFalse(StudentProfileFormat.isValidJalaliDate("1404/08/21 extra"))
        assertFalse(StudentProfileFormat.isValidJalaliDate("21/08/1404"))
    }

    // ── دو هلپرِ همسایه که در همان object منتقل شدند ──

    @Test fun formatCurrencyGroupsThousandsAndDropsTheSign() {
        assertEquals("1,234,567", StudentProfileFormat.formatCurrency(1_234_567))
        assertEquals("5,000", StudentProfileFormat.formatCurrency(-5_000))
        assertEquals("0", StudentProfileFormat.formatCurrency(0))
        assertEquals("999", StudentProfileFormat.formatCurrency(999))
    }

    @Test fun normalizePersianDigitsConvertsBothDigitSetsAndKeepsLatin() {
        assertEquals("1404/08/21", StudentProfileFormat.normalizePersianDigits("۱۴۰۴/۰۸/۲۱"))
        assertEquals("1404/08/21", StudentProfileFormat.normalizePersianDigits("١٤٠٤/٠٨/٢١"))
        assertEquals("1404/08/21", StudentProfileFormat.normalizePersianDigits("1404/08/21"))
        assertEquals("12,000", StudentProfileFormat.normalizePersianDigits("۱۲,۰۰۰"))
    }
}
