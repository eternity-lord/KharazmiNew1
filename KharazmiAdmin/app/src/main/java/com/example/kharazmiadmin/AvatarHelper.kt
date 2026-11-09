package com.example.kharazmiadmin

import android.content.Context
import android.graphics.*
import android.graphics.drawable.BitmapDrawable
import android.graphics.drawable.Drawable

object AvatarHelper {
    // ۸ رنگ ملایم و هماهنگ با پلتفرم خوارزمی
    private val colors = arrayOf(
        "#4DB6AC", // سبز کله‌غازی ملایم
        "#81C784", // سبز ملایم
        "#64B5F6", // آبی ملایم
        "#BA68C8", // بنفش ملایم
        "#FF8A65", // مرجانی ملایم
        "#FFD54F", // زرد ملایم
        "#4DD0E1", // فیروزه‌ای ملایم
        "#A1887F"  // قهوه‌ای ملایم
    )

    fun getAvatar(context: Context, name: String, id: Int): Drawable {
        val initial = if (name.isNotEmpty()) name.trim().substring(0, 1) else "?"
        
        // انتخاب رنگ بر اساس هش فیلد نام یا شناسه
        val colorHex = colors[Math.abs(name.hashCode() + id) % colors.size]
        val color = Color.parseColor(colorHex)
        
        val size = 120 // سایز بهینه برای لیست و پروفایل
        val bitmap = Bitmap.createBitmap(size, size, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(bitmap)
        
        // رسم دایره رنگی پس‌زمینه
        val paint = Paint().apply {
            isAntiAlias = true
            this.color = color
            style = Paint.Style.FILL
        }
        canvas.drawCircle(size / 2f, size / 2f, size / 2f, paint)
        
        // رسم کاراکتر اول نام به صورت بولد و سفید در مرکز دایره
        val textPaint = Paint().apply {
            isAntiAlias = true
            this.color = Color.WHITE
            textSize = 50f
            typeface = Typeface.create("sans-serif-medium", Typeface.BOLD)
            textAlign = Paint.Align.CENTER
        }
        
        val textRect = Rect()
        textPaint.getTextBounds(initial, 0, initial.length, textRect)
        val textHeight = textRect.height()
        val textY = (size / 2f) + (textHeight / 2f) - 4f
        
        canvas.drawText(initial, size / 2f, textY, textPaint)
        
        return BitmapDrawable(context.resources, bitmap)
    }
}
