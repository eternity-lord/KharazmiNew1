package com.example.kharazmiadmin

import android.content.Context
import android.content.res.ColorStateList
import android.graphics.Color
import android.util.AttributeSet
import android.view.MotionEvent
import android.view.View
import android.view.ViewGroup
import android.view.animation.OvershootInterpolator
import android.widget.ProgressBar
import androidx.core.content.ContextCompat
import androidx.core.view.ViewCompat
import kotlin.math.roundToInt
import com.google.android.material.button.MaterialButton

/**
 * GoldButton - دکمه اصلی طلایی با انیمیشن‌های کامل
 * 
 * رفتار:
 * 1. Press: scale 1.0 -> 0.96 در 100ms (OvershootInterpolator)، glow alpha 100% -> 60%
 * 2. Release: scale 1.0 با spring/overshoot در 150ms
 * 3. Ripple: طلایی روشن‌تر (gold_primary_light با alpha 40%)
 * 4. Loading state: ProgressBar واقعی وسط دکمه، بدون تغییر اندازه یا حذف برچسب
 * 5. Disabled: gradient خاکستری تیره با متن text_disabled، بدون گلو
 * 
 * استفاده: در XML به جای MaterialButton از com.example.kharazmiadmin.GoldButton
 * یا استایل Widget.Kharazmi.Button.Gold
 */
class GoldButton @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyleAttr: Int = R.style.Widget_Kharazmi_Button_Gold
) : MaterialButton(context, attrs, defStyleAttr) {

    private var isLoading = false
    // FIX: Gold loading is a real child of the parent's overlay; MaterialButton itself is not a ViewGroup.
    private var progressBar: ProgressBar? = null
    private var progressParent: ViewGroup? = null
    private var enabledBeforeLoading = true
    private var textColorsBeforeLoading: ColorStateList? = null
    private var iconTintBeforeLoading: ColorStateList? = null
    private var stateDescriptionBeforeLoading: CharSequence? = null

    init {
        // تنظیمات اولیه طلایی
        cornerRadius = (14 * resources.displayMetrics.density).toInt()
        isAllCaps = false
        // متن مشکی روی طلایی طبق قانون کنتراست
        // FIX: Keep disabled text readable even when the button is initially disabled in XML.
        setTextColor(ContextCompat.getColorStateList(context, R.color.gold_button_text))
        addOnLayoutChangeListener { _, _, _, _, _, _, _, _, _ ->
            if (isLoading) showLoadingIndicator()
        }

        // Ripple طلایی
        rippleColor = android.content.res.ColorStateList.valueOf(
            ContextCompat.getColor(context, R.color.gold_ripple)
        )

        // انیمیشن کلیک - scale
        setupPressAnimation()
    }

    private fun setupPressAnimation() {
        // Press/Release با ViewPropertyAnimator
        setOnTouchListener { v, event ->
            if (isLoading || !isEnabled) return@setOnTouchListener false
            
            when (event.action) {
                MotionEvent.ACTION_DOWN -> {
                    // Press: scale 0.96 در 100ms
                    v.animate()
                        .scaleX(0.96f)
                        .scaleY(0.96f)
                        .setDuration(100)
                        .setInterpolator(OvershootInterpolator(0.5f))
                        .start()
                    // Glow alpha کم
                    v.alpha = 0.9f
                }
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                    // Release: برگشت با spring
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

    override fun setEnabled(enabled: Boolean) {
        super.setEnabled(enabled)
        if (enabled) {
            alpha = 1.0f
            // برگرداندن gradient طلایی
            background = ContextCompat.getDrawable(context, R.drawable.bg_button_gold_selector)
            setTextColor(ContextCompat.getColor(context, R.color.text_on_gold))
            elevation = 4 * resources.displayMetrics.density
        } else {
            // Disabled: خاکستری تیره بدون گلو
            alpha = 1.0f
            background = ContextCompat.getDrawable(context, R.drawable.bg_button_gold_disabled)
            setTextColor(ContextCompat.getColor(context, R.color.text_disabled))
            elevation = 0f
        }
    }

    /** Show progress without shrinking a wrap-content label or discarding its accessible name. */
    fun setLoading(loading: Boolean) {
        if (isLoading == loading) return
        // FIX: Rapid start/stop must not leave an old fade callback hiding the label later.
        animate().cancel()
        scaleX = 1f
        scaleY = 1f
        alpha = 1f
        if (loading) {
            enabledBeforeLoading = isEnabled
            textColorsBeforeLoading = textColors
            iconTintBeforeLoading = iconTint
            stateDescriptionBeforeLoading = ViewCompat.getStateDescription(this)
            isLoading = true
            isEnabled = false
            // FIX: Hide only foreground paint, not text/icon bounds, so the button keeps its width.
            setTextColor(Color.TRANSPARENT)
            iconTint = ColorStateList.valueOf(Color.TRANSPARENT)
            ViewCompat.setStateDescription(this, context.getString(R.string.message_loading))
            showLoadingIndicator()
        } else {
            isLoading = false
            removeLoadingIndicator()
            isEnabled = enabledBeforeLoading
            textColorsBeforeLoading?.let { setTextColor(it) }
            iconTint = iconTintBeforeLoading
            ViewCompat.setStateDescription(this, stateDescriptionBeforeLoading)
        }
    }

    private fun showLoadingIndicator() {
        val host = parent as? ViewGroup ?: return
        if (!isAttachedToWindow || width == 0 || height == 0) return
        val spinner = progressBar ?: ProgressBar(context).apply {
            isIndeterminate = true
            indeterminateTintList = ColorStateList.valueOf(ContextCompat.getColor(context, R.color.gold_primary))
            // FIX: The button's loading state is announced; do not add a second accessibility focus target.
            importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO
        }.also { progressBar = it }
        if (progressParent !== host) {
            progressParent?.overlay?.remove(spinner)
            host.overlay.add(spinner)
            progressParent = host
        }
        // FIX: An overlay does not measure its children: explicitly size and center the real ProgressBar.
        val size = (20 * resources.displayMetrics.density).roundToInt().coerceAtMost(minOf(width, height))
        val spec = View.MeasureSpec.makeMeasureSpec(size, View.MeasureSpec.EXACTLY)
        spinner.measure(spec, spec)
        val left = (x + (width - size) / 2f).roundToInt()
        val top = (y + (height - size) / 2f).roundToInt()
        spinner.layout(left, top, left + size, top + size)
        spinner.visibility = View.VISIBLE
    }

    private fun removeLoadingIndicator() {
        progressBar?.let {
            it.visibility = View.GONE
            progressParent?.overlay?.remove(it)
        }
        progressParent = null
    }

    override fun onAttachedToWindow() {
        super.onAttachedToWindow()
        // FIX: setLoading may have been called before the button was attached or laid out.
        if (isLoading) showLoadingIndicator()
    }

    override fun onDetachedFromWindow() {
        // FIX: Never leave a spinner in the old parent's overlay after navigating away.
        removeLoadingIndicator()
        super.onDetachedFromWindow()
    }

    fun isLoading(): Boolean = isLoading
}
