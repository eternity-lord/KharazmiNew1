package com.example.kharazmiadmin

import android.annotation.SuppressLint
import android.view.MotionEvent
import android.view.View

object ButtonAnimator {
    @SuppressLint("ClickableViewAccessibility")
    fun applyPillScaleAnimation(view: View) {
        if (!AnimationConstants.areAnimationsEnabled(view.context)) {
            return
        }
        view.setOnTouchListener { v, event ->
            when (event.action) {
                MotionEvent.ACTION_DOWN -> {
                    v.animate()
                        .scaleX(0.97f)
                        .scaleY(0.97f)
                        .setDuration(AnimationConstants.ANIM_MICRO)
                        .start()
                }
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                    v.animate()
                        .scaleX(1.0f)
                        .scaleY(1.0f)
                        .setDuration(AnimationConstants.ANIM_MICRO)
                        .start()
                }
            }
            false // اجازه برقراری کلیک ران شود
        }
    }
}
