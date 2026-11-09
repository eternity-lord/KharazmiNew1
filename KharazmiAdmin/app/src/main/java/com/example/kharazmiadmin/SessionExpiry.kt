package com.example.kharazmiadmin

// FIX M30: فلگ سبک «نشست منقضی شد» با گارد یک‌بارمصرف — جایگزین پرتاب مستقیم CLEAR_TASK از اینترسپتور.
// اینترسپتور فقط signal می‌کند؛ نمایش دیالوگ با هاست (BaseActivity.onResume) است.
object SessionExpiry {
    private var signaled = false
    private var dialogShowing = false

    @Synchronized
    fun signal() {
        signaled = true
    }

    // true فقط برای اولین هاست پس از سیگنال، وقتی دیالوگی بالا نیست (401های موازی → فقط یک دیالوگ).
    @Synchronized
    fun claim(): Boolean {
        if (signaled && !dialogShowing) {
            dialogShowing = true
            return true
        }
        return false
    }

    // بسته‌شدن دیالوگ (بک/تاچ بیرون/چرخش صفحه): فلگ می‌ماند تا در resume بعدی یادآوری شود.
    @Synchronized
    fun onDialogGone() {
        dialogShowing = false
    }

    // فقط دکمه‌ی «ورود مجدد»: ریست کامل فلگ.
    @Synchronized
    fun reset() {
        signaled = false
        dialogShowing = false
    }
}
