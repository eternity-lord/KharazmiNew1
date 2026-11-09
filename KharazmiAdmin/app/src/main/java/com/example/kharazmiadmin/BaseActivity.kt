package com.example.kharazmiadmin

import android.content.Intent
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity

// FIX M30: بیس مشترک همه‌ی اکتیویتی‌ها — هاست دیالوگ «نشست منقضی شد» در onResume.
open class BaseActivity : AppCompatActivity() {

    private var sessionDialog: AlertDialog? = null

    override fun onResume() {
        super.onResume()
        // FIX M30: خودِ صفحه‌ی لاگین دیالوگ انقضا نمی‌خواهد.
        if (this is LoginActivity) return
        if (isFinishing) return
        if (SessionExpiry.claim()) {
            val dialog = AlertDialog.Builder(this)
                .setTitle(getString(R.string.bact_sess_title))
                .setMessage(getString(R.string.bact_sess_msg))
                .setCancelable(true)  // FIX M30: غیرمدال — با بک/تاچ بیرون به فرم برمی‌گردد؛ یادآوری در resume بعدی.
                .setPositiveButton(getString(R.string.bact_relogin)) { _, _ ->
                    // FIX M30: فقط اینجا واقعاً خروج می‌دهیم — ریست فلگ + لاگین با CLEAR_TASK.
                    SessionExpiry.reset()
                    val intent = Intent(this, LoginActivity::class.java).apply {
                        addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK)
                    }
                    startActivity(intent)
                }
                .create()
            dialog.setOnDismissListener { SessionExpiry.onDialogGone() }
            sessionDialog = dialog
            dialog.show()
        }
    }

    override fun onPause() {
        // FIX M30: بستن دیالوگ هنگام ترک صفحه تا Window leak نشود؛ فلگ سیگنال می‌ماند
        // و در صفحه‌ی بعدی دوباره نشان داده می‌شود.
        sessionDialog?.dismiss()
        sessionDialog = null
        super.onPause()
    }
}
