package com.example.kharazmiadmin

import android.content.Context

/**
 * برچسب‌های نمایشی «یک کلاس از یک دانش‌آموز» — مشترک بین صدور حواله (InvoiceActivity) و
 * پروفایل دانش‌آموز (StudentProfileActivity) تا هر دو دقیقاً یک متن بسازند.
 *
 * قرارداد مهم: هر برچسب فقط از داده‌ی «همان کلاس» ساخته می‌شود (بدهی، معلم، تعداد جلسه)؛
 * دو کلاسِ یک دانش‌آموز که معلم مشترک دارند هرگز جمع نمی‌شوند. هیچ‌جا شناسه از روی این متن
 * استخراج نمی‌شود (فقط UI).
 */
object EnrollmentLabels {

    /** «ریاضی (کد: 100002)» — فقط عنوان و کد کلاس، بدون بدهی (برای «کلاس انتخاب‌شده» و رسید). */
    fun classTitle(context: Context, en: ActiveStudentEnrollment): String {
        val title = (en.course_title ?: en.title)?.trim().orEmpty()
        val code = en.code?.trim().orEmpty()
        return classTitle(context, title, code)
    }

    fun classTitle(context: Context, title: String?, code: String?): String {
        val t = title?.trim().orEmpty()
        val c = code?.trim().orEmpty()
        return when {
            t.isNotEmpty() && c.isNotEmpty() -> context.getString(R.string.enroll_label_class, t, c)
            t.isNotEmpty() -> t
            c.isNotEmpty() -> c
            else -> context.getString(R.string.common_unknown_class)
        }
    }

    /** خط «بدهی به معلم (نام معلم): X تومان» — نام معلم جلوی خود بدهی می‌آید. */
    fun debtTeacherLine(context: Context, teacherName: String?, debt: Long?): String {
        val amount = String.format("%,d", debt ?: 0L)
        val name = teacherName?.trim().orEmpty()
        return if (name.isNotEmpty()) context.getString(R.string.enroll_label_debt_teacher_named, name, amount)
        else context.getString(R.string.enroll_label_debt_teacher, amount)
    }

    fun debtInstituteLine(context: Context, debt: Long?): String =
        context.getString(R.string.enroll_label_debt_institute, String.format("%,d", debt ?: 0L))

    /**
     * «این مبلغ برای چند جلسه است؟» — null وقتی سرور قدیمی است و شمارش جلسه نمی‌فرستد
     * (تا متن اشتباه/حدسی نمایش داده نشود).
     */
    fun sessionsLine(
        context: Context,
        sessionsBilled: Int?,
        unpaidSessions: Int?,
        contractOnly: Boolean,
    ): String? {
        if (sessionsBilled == null) return null
        return when {
            contractOnly -> context.getString(R.string.enroll_label_contract_only)
            sessionsBilled == 0 -> context.getString(R.string.enroll_label_sessions_none)
            (unpaidSessions ?: 0) == 0 -> context.getString(R.string.enroll_label_sessions_settled)
            else -> context.getString(R.string.enroll_label_sessions, unpaidSessions.toString(), sessionsBilled.toString())
        }
    }

    /**
     * متن چندخطی هر ردیفِ پاپ‌آپ «انتخاب کلاس»:
     * کلاس (کد) / معلم / بدهی به معلم (نام معلم) / بدهی به آموزشگاه / برای چند جلسه.
     */
    fun pickerLabel(context: Context, en: ActiveStudentEnrollment): String {
        val lines = ArrayList<String>()
        lines.add(classTitle(context, en))
        val teacher = en.teacher_name?.trim().orEmpty()
        if (teacher.isNotEmpty()) lines.add(context.getString(R.string.enroll_label_teacher, teacher))
        lines.add(debtTeacherLine(context, teacher, en.debt_teacher))
        lines.add(debtInstituteLine(context, en.debt_institute))
        sessionsLine(context, en.sessions_billed, en.unpaid_sessions, en.contract_only)?.let { lines.add(it) }
        return lines.joinToString("\n")
    }
}
