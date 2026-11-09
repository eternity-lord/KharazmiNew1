package com.example.kharazmiadmin

import android.content.Context
import androidx.annotation.ColorRes
import androidx.core.content.ContextCompat

/**
 * Single entry point for runtime UI colors.
 *
 * Resolving semantic colors through resources keeps adapters, dialogs and charts in
 * sync with the active day/night palette instead of baking a light-only hex value
 * into a view at runtime.
 */
object UiColors {
    fun resolve(context: Context, @ColorRes resource: Int): Int =
        ContextCompat.getColor(context, resource)
}
