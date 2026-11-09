package com.example.kharazmiadmin

import android.animation.ValueAnimator
import android.widget.TextView
import java.util.Locale

object NumberAnimator {
    fun animateNumber(textView: TextView, from: Long, to: Long, suffix: String? = null) {
        // L5: پسوند « تومان» از ریسورس؛ null یعنی پیش‌فرض (هر دو caller فعلی پیش‌فرض می‌گیرند).
        val sfx = suffix ?: (" " + textView.context.getString(R.string.attendance_toman))
        if (!AnimationConstants.areAnimationsEnabled(textView.context)) {
            textView.text = String.format(Locale("en", "US"), "%,d", to) + sfx
            return
        }
        val animator = ValueAnimator.ofInt(from.toInt(), to.toInt())
        animator.duration = 350L // 350 ms timing (between 300-400ms)
        animator.addUpdateListener { animation ->
            val value = (animation.animatedValue as? Int)?.toLong() ?: to
            textView.text = String.format(Locale("en", "US"), "%,d", value) + sfx
        }
        animator.start()
    }
}
