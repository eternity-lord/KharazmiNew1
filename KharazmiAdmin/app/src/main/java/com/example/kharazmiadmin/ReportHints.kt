package com.example.kharazmiadmin

import android.content.Context
import android.view.View
import android.widget.TextView

/**
 * متن توضیحی زیر کارت «آمار مالی ماهانه»: چرا صفر است و پیش‌پرداخت‌ها کجا حساب می‌شوند.
 * فقط نمایش است؛ هیچ عدد مالی را تغییر نمی‌دهد. سرور قدیمی `diagnostics` نمی‌فرستد ⇒ پنهان.
 */
object ReportHints {
    fun lines(context: Context, monthly: FinancialMetrics, d: ReportDiagnostics?): List<String> {
        if (d == null) return emptyList()
        val out = mutableListOf<String>()
        if (monthly.total == 0L) {
            when {
                d.session_charges_total == 0 -> out += context.getString(R.string.rpt_hint_no_sessions)
                d.session_charges_in_period == 0 && !d.last_session_charge_date.isNullOrBlank() ->
                    out += context.getString(R.string.rpt_hint_month_empty, d.last_session_charge_date)
                d.session_charges_in_period == 0 -> out += context.getString(R.string.rpt_hint_month_empty_undated, d.session_charges_undated)
                else -> out += context.getString(R.string.rpt_hint_zero_share)
            }
        }
        if (d.prepaid_amount > 0) {
            out += context.getString(R.string.rpt_hint_prepaid, d.prepaid_count, String.format("%,d", d.prepaid_amount))
        }
        return out
    }

    fun bind(context: Context, view: TextView?, monthly: FinancialMetrics, d: ReportDiagnostics?) {
        view ?: return
        val lines = lines(context, monthly, d)
        if (lines.isEmpty()) {
            view.visibility = View.GONE
            view.text = ""
        } else {
            view.text = lines.joinToString("\n")
            view.visibility = View.VISIBLE
        }
    }
}
