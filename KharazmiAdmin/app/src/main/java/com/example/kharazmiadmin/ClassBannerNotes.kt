package com.example.kharazmiadmin

import android.view.View
import android.widget.TextView

/**
 * یادداشت زیر اعداد مالی بنر کلاس (مدیریت کلاس‌ها و پنل معلم).
 *
 * هدف شفافیت است: بدهی نمایش‌داده‌شده فقط مال «همین کلاس» است و بابت چند جلسهٔ ثبت‌شدهٔ همین کلاس.
 * فقط نمایش است و هیچ عدد مالی را تغییر نمی‌دهد. سرور قدیمی فیلد را نمی‌فرستد ⇒ یادداشت پنهان.
 */
object ClassBannerNotes {
    fun debtNoteRes(unpaidSessions: Int?, sessionsBilled: Int?, debtTeacher: Long, debtInstitute: Long): Int? {
        if (unpaidSessions == null && sessionsBilled == null) return null   // سرور قدیمی
        if ((unpaidSessions ?: 0) > 0) return R.string.banner_debt_sessions
        if ((sessionsBilled ?: 0) == 0 && debtTeacher + debtInstitute > 0) return R.string.banner_debt_contract
        return null
    }

    fun bindDebtNote(view: TextView, unpaidSessions: Int?, sessionsBilled: Int?, debtTeacher: Long, debtInstitute: Long) {
        val res = debtNoteRes(unpaidSessions, sessionsBilled, debtTeacher, debtInstitute)
        if (res == null) {
            view.visibility = View.GONE
            view.text = ""
        } else {
            view.text = if (res == R.string.banner_debt_sessions)
                view.context.getString(res, unpaidSessions ?: 0)
            else view.context.getString(res)
            view.visibility = View.VISIBLE
        }
    }
}
