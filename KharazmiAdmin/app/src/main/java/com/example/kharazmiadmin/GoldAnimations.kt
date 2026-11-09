package com.example.kharazmiadmin

import android.animation.*
import android.view.View
import androidx.core.view.doOnLayout
import kotlin.math.roundToInt
import android.view.animation.DecelerateInterpolator
import android.view.animation.OvershootInterpolator
import android.widget.EditText
import androidx.core.content.ContextCompat
import com.google.android.material.card.MaterialCardView
import com.google.android.material.textfield.TextInputLayout

/**
 * GoldAnimations - تمام انیمیشن‌های تم طلایی/تیره
 * 
 * این کلاس فقط UI helper است، هیچ منطق بیزینسی یا API ندارد
 * طبق قانون طلایی پرامپت: فقط لایه ظاهری
 */
object GoldAnimations {

    // ==================== BUTTON ANIMATIONS ====================

    /**
     * دکمه طلایی - Press: scale 1.0 -> 0.96 در 100ms
     */
    fun applyGoldButtonPressAnimation(button: View) {
        button.setOnTouchListener { v, event ->
            when (event.action) {
                android.view.MotionEvent.ACTION_DOWN -> {
                    v.animate()
                        .scaleX(0.96f)
                        .scaleY(0.96f)
                        .setDuration(100)
                        .setInterpolator(OvershootInterpolator(0.5f))
                        .start()
                    v.alpha = 0.9f
                }
                android.view.MotionEvent.ACTION_UP, android.view.MotionEvent.ACTION_CANCEL -> {
                    v.animate()
                        .scaleX(1.0f)
                        .scaleY(1.0f)
                        .setDuration(150)
                        .setInterpolator(OvershootInterpolator(1.5f))
                        .start()
                    v.alpha = 1.0f
                }
            }
            false
        }
    }

    /**
     * دکمه لودینگ - fade-out متن و fade-in progress
     */
    fun animateButtonLoading(button: View, loading: Boolean, originalText: CharSequence, progressView: View?) {
        if (loading) {
            button.animate().alpha(0f).setDuration(150).withEndAction {
                // در پیاده‌سازی کامل: progressView visible
                progressView?.visibility = View.VISIBLE
                progressView?.alpha = 0f
                progressView?.animate()?.alpha(1f)?.setDuration(150)?.start()
                button.alpha = 0.8f
                button.isEnabled = false
            }.start()
        } else {
            progressView?.animate()?.alpha(0f)?.setDuration(150)?.withEndAction {
                progressView.visibility = View.GONE
                button.animate().alpha(1f).setDuration(150).start()
                button.isEnabled = true
            }?.start()
        }
    }

    // ==================== CARD ANIMATIONS ====================

    /**
     * کارت قابل کلیک - لمس: بوردر از subtle به gold در 150ms
     */
    fun applyGoldCardTouchAnimation(card: MaterialCardView) {
        val defaultStroke = ContextCompat.getColor(card.context, R.color.gold_border_subtle)
        val focusedStroke = ContextCompat.getColor(card.context, R.color.gold_primary)

        card.setOnTouchListener { v, event ->
            when (event.action) {
                android.view.MotionEvent.ACTION_DOWN -> {
                    // انیمیت رنگ بوردر
                    val colorAnim = ValueAnimator.ofArgb(defaultStroke, focusedStroke)
                    colorAnim.duration = 150
                    colorAnim.addUpdateListener { animator ->
                        (v as MaterialCardView).strokeColor = animator.animatedValue as Int
                    }
                    colorAnim.start()
                }
                android.view.MotionEvent.ACTION_UP, android.view.MotionEvent.ACTION_CANCEL -> {
                    val colorAnim = ValueAnimator.ofArgb(focusedStroke, defaultStroke)
                    colorAnim.duration = 150
                    colorAnim.addUpdateListener { animator ->
                        (v as MaterialCardView).strokeColor = animator.animatedValue as Int
                    }
                    colorAnim.start()
                }
            }
            false
        }
    }

    /**
     * کارت برجسته/فوری - pulse آرام روی بوردر طلایی (alpha 100% -> 40%، چرخه 2s)
     */
    fun applyGoldCardPulseAnimation(card: MaterialCardView) {
        val pulse = ObjectAnimator.ofFloat(card, "alpha", 1f, 0.6f, 1f).apply {
            duration = 2000
            repeatCount = ValueAnimator.INFINITE
            interpolator = DecelerateInterpolator()
        }
        // برای بوردر، از stroke alpha استفاده می‌کنیم - ساده‌سازی: alpha کل کارت
        // در پیاده‌سازی پیشرفته‌تر باید drawable جداگانه pulse شود
        pulse.start()
        card.tag = pulse // برای stop بعدی
    }

    fun stopGoldCardPulseAnimation(card: MaterialCardView) {
        (card.tag as? ObjectAnimator)?.cancel()
        card.alpha = 1f
    }

    // ==================== INPUT ANIMATIONS ====================

    /**
     * فوکوس روی فیلد ورودی: خط از خاکستری به طلایی در 200ms
     */
    fun applyGoldInputFocusAnimation(inputLayout: TextInputLayout) {
        val editText = inputLayout.editText ?: return
        val defaultColor = ContextCompat.getColor(inputLayout.context, R.color.gold_border_subtle)
        val focusedColor = ContextCompat.getColor(inputLayout.context, R.color.gold_primary)

        editText.setOnFocusChangeListener { _, hasFocus ->
            val from = if (hasFocus) defaultColor else focusedColor
            val to = if (hasFocus) focusedColor else defaultColor
            
            val colorAnim = ValueAnimator.ofArgb(from, to)
            colorAnim.duration = 200
            colorAnim.addUpdateListener { animator ->
                inputLayout.boxStrokeColor = animator.animatedValue as Int
                inputLayout.hintTextColor = android.content.res.ColorStateList.valueOf(animator.animatedValue as Int)
            }
            colorAnim.start()
        }
    }

    /**
     * حالت خطا: قرمز + لرزش افقی ظریف (0 -> 8 -> -8 -> 4 -> 0 در 300ms)
     */
    fun applyGoldInputErrorShake(view: View, inputLayout: TextInputLayout? = null) {
        // تغییر رنگ به قرمز
        inputLayout?.let {
            it.boxStrokeColor = ContextCompat.getColor(it.context, R.color.status_danger)
        }

        // لرزش افقی
        val shake = ObjectAnimator.ofFloat(view, "translationX", 0f, 8f, -8f, 4f, -4f, 0f).apply {
            duration = 300
            interpolator = DecelerateInterpolator()
        }
        shake.start()
    }

    // ==================== OTP BOX ANIMATIONS ====================

    /**
     * OTP باکس: رقم وارد شد -> بوردر طلایی + scale 1.0->1.08->1.0 در 150ms
     */
    fun animateOtpFilled(view: View) {
        view.background = ContextCompat.getDrawable(view.context, R.drawable.bg_otp_box_filled)
        view.animate()
            .scaleX(1.08f)
            .scaleY(1.08f)
            .setDuration(75)
            .withEndAction {
                view.animate()
                    .scaleX(1f)
                    .scaleY(1f)
                    .setDuration(75)
                    .start()
            }
            .start()
    }

    fun animateOtpError(views: List<View>) {
        views.forEach { v ->
            v.background = ContextCompat.getDrawable(v.context, R.drawable.bg_otp_box_error)
        }
        // لرزش کل ردیف
        if (views.isNotEmpty()) {
            val parent = views[0].parent as? View ?: views[0]
            val shake = ObjectAnimator.ofFloat(parent, "translationX", 0f, 12f, -12f, 8f, -8f, 0f).apply {
                duration = 300
            }
            shake.start()
            // FIX: Clear only error styling, never entered digits, focus or the user's caret/selection.
            parent.postDelayed({
                views.forEach { v ->
                    val background = if (v.hasFocus() || (v is EditText && v.text.isNotEmpty())) {
                        R.drawable.bg_otp_box_filled
                    } else {
                        R.drawable.bg_otp_box
                    }
                    v.background = ContextCompat.getDrawable(v.context, background)
                }
            }, 400)
        }
    }

    // ==================== PROGRESS CIRCLE ====================

    /**
     * دایره پیشرفت: arc از 0 به مقدار واقعی در 800ms + count-up عدد
     */
    fun animateCircularProgress(progressView: View, targetProgress: Int, textView: android.widget.TextView) {
        val animator = ValueAnimator.ofInt(0, targetProgress)
        animator.duration = 800
        animator.interpolator = DecelerateInterpolator()
        animator.addUpdateListener { animation ->
            val value = animation.animatedValue as Int
            // در اینجا باید progress دایره‌ای آپدیت شود
            textView.text = "$value%"
        }
        animator.start()
    }

    // ==================== CHAT BUBBLES ====================

    /**
     * پیام جدید: slide-up + fade-in از پایین در 200ms
     */
    fun animateChatMessageIn(view: View) {
        view.alpha = 0f
        view.translationY = 50f
        view.animate()
            .alpha(1f)
            .translationY(0f)
            .setDuration(200)
            .setInterpolator(DecelerateInterpolator())
            .start()
    }

    // ==================== LIST ANIMATIONS (staggered) ====================

    fun applyStaggeredListAnimation(recyclerView: androidx.recyclerview.widget.RecyclerView) {
        // از قبل پیاده‌سازی شده، دست نزن - فقط placeholder
        // layout_animation_fall_down موجود حفظ می‌شود
    }

    // ==================== BOTTOM NAV ====================

    /**
     * Animate the underline to the selected tab's measured width. Call after layout.
     * X offsets use the starting layout-left, as in the original translation-only API.
     */
    @JvmOverloads
    fun animateBottomNavIndicator(indicator: View, fromX: Float, toX: Float, toWidth: Int = indicator.width) {
        val params = indicator.layoutParams ?: return
        // FIX: Quick tab changes continue from the visible position/width, not an obsolete tab's bounds.
        val previous = indicator.getTag(R.id.gold_nav_indicator_animator) as? ValueAnimator
        val startX = if (previous?.isRunning == true) indicator.translationX else fromX
        previous?.cancel()
        val startWidth = if (params.width >= 0) params.width else indicator.width
        val endWidth = toWidth.coerceAtLeast(0)
        val layoutLeft = indicator.left.toFloat()
        var visualLeft = layoutLeft + startX
        val animator = ValueAnimator.ofFloat(0f, 1f)
        // FIX: Keep the visual left edge stable when an RTL/right-anchored parent repositions the resized view.
        val onLayout = View.OnLayoutChangeListener { view, _, _, _, _, _, _, _, _ ->
            view.translationX = visualLeft - view.left
        }
        val onAttach = object : View.OnAttachStateChangeListener {
            override fun onViewAttachedToWindow(view: View) = Unit
            override fun onViewDetachedFromWindow(view: View) { animator.cancel() }
        }
        indicator.addOnLayoutChangeListener(onLayout)
        indicator.addOnAttachStateChangeListener(onAttach)
        animator.duration = if (AnimationConstants.areAnimationsEnabled(indicator.context)) 200 else 0
        animator.interpolator = DecelerateInterpolator()
        animator.addUpdateListener {
            val fraction = it.animatedValue as Float
            visualLeft = layoutLeft + startX + (toX - startX) * fraction
            // FIX: Resize the actual underline, preserving rounded caps instead of stretching it with scaleX.
            val width = (startWidth + (endWidth - startWidth) * fraction).roundToInt()
            if (params.width != width) {
                params.width = width
                indicator.layoutParams = params
            }
            indicator.translationX = visualLeft - indicator.left
        }
        animator.addListener(object : AnimatorListenerAdapter() {
            private var cancelled = false
            override fun onAnimationCancel(animation: Animator) { cancelled = true }
            override fun onAnimationEnd(animation: Animator) {
                indicator.removeOnLayoutChangeListener(onLayout)
                indicator.removeOnAttachStateChangeListener(onAttach)
                if (!cancelled) {
                    // FIX: Align once more after the final width's layout; an obsolete callback cannot move a new animation.
                    indicator.doOnLayout { view ->
                        if (view.getTag(R.id.gold_nav_indicator_animator) === animator) {
                            view.translationX = visualLeft - view.left
                            view.setTag(R.id.gold_nav_indicator_animator, null)
                        }
                    }
                } else if (indicator.getTag(R.id.gold_nav_indicator_animator) === animator) {
                    indicator.setTag(R.id.gold_nav_indicator_animator, null)
                }
            }
        })
        indicator.setTag(R.id.gold_nav_indicator_animator, animator)
        animator.start()
    }
}
