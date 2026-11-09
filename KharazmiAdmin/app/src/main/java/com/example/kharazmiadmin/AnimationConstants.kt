package com.example.kharazmiadmin

import android.content.Context
import android.provider.Settings

object AnimationConstants {
    const val ANIM_MICRO: Long = 120L // تغییر حالت دکمه، چک‌باکس
    const val ANIM_TRANSITION: Long = 280L // انتقال بین صفحات
    const val ANIM_STAGGER_DELAY: Long = 40L // فاصله لود هر آیتم لیست

    // بررسی مقتدرانه تنظیم سیستمی کاهش انیمیشن کاربر (Accessibility / Reduce Motion)
    fun areAnimationsEnabled(context: Context): Boolean {
        return try {
            val scale = Settings.Global.getFloat(
                context.contentResolver,
                Settings.Global.ANIMATOR_DURATION_SCALE,
                1.0f
            )
            scale > 0.0f
        } catch (e: Exception) {
            true
        }
    }
}
