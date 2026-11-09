package com.example.kharazmiadmin

import android.app.Activity
import android.content.Context
import android.graphics.Color
import android.view.Gravity
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.LinearLayout
import android.widget.TextView
import com.google.gson.Gson
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.lang.reflect.Type

object CachedApiCall {

    // قالب‌بندی زمان خورشیدی گذشته از آخرین آپدیت
    fun getOfflineTimeString(context: Context, timestamp: Long): String {
        val diff = System.currentTimeMillis() - timestamp
        val seconds = diff / 1000
        val minutes = seconds / 60
        val hours = minutes / 60
        val days = hours / 24

        return when {
            days > 0 -> context.getString(R.string.capi_days_ago, days)
            hours > 0 -> context.getString(R.string.capi_hours_ago, hours)
            minutes > 0 -> context.getString(R.string.capi_mins_ago, minutes)
            else -> context.getString(R.string.capi_just_now)
        }
    }

    // لود پویای اسکلت شیمر روی صفحه در زمان دریافت دیتا
    fun showShimmer(activity: Activity) {
        val root = activity.findViewById<ViewGroup>(android.R.id.content)
        val shimmerId = 887766
        var shimmerView = root.findViewById<View>(shimmerId)

        if (shimmerView == null) {
            shimmerView = LayoutInflater.from(activity).inflate(R.layout.layout_loading, root, false).apply {
                id = shimmerId
            }
            root.addView(shimmerView)
            
            // شروع انیمیشن شیمر
            val container = shimmerView.findViewById<com.facebook.shimmer.ShimmerFrameLayout>(R.id.shimmer_view_container)
            container?.startShimmer()
        } else {
            shimmerView.visibility = View.VISIBLE
            val container = shimmerView.findViewById<com.facebook.shimmer.ShimmerFrameLayout>(R.id.shimmer_view_container)
            container?.startShimmer()
        }
    }

    fun hideShimmer(activity: Activity) {
        val root = activity.findViewById<ViewGroup>(android.R.id.content)
        val shimmerView = root.findViewById<View>(887766)
        if (shimmerView != null) {
            val container = shimmerView.findViewById<com.facebook.shimmer.ShimmerFrameLayout>(R.id.shimmer_view_container)
            container?.stopShimmer()
            root.removeView(shimmerView)
        }
    }

    // تزریق پویای نشانگر زرد رنگ داده آفلاین به بالای صفحه بدون تغییر فایل‌های XML
    fun showOfflineBanner(activity: Activity, timestamp: Long) {
        val root = activity.findViewById<ViewGroup>(android.R.id.content)
        val bannerId = 998877
        var banner = root.findViewById<TextView>(bannerId)

        val timeStr = getOfflineTimeString(activity, timestamp)
        val text = activity.getString(R.string.capi_offline_banner, timeStr)

        if (banner == null) {
            banner = TextView(activity).apply {
                id = bannerId
                layoutParams = ViewGroup.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    ViewGroup.LayoutParams.WRAP_CONTENT
                )
                setBackgroundColor(UiColors.resolve(activity, R.color.status_warning_light)) // زرد کم‌رنگ
                setTextColor(UiColors.resolve(activity, R.color.status_warning)) // نارنجی تیره
                setPadding(24, 16, 24, 16)
                textSize = 13f
                gravity = Gravity.CENTER
                setText(text)
            }
            root.addView(banner, 0) // افزودن به بالاترین بخش کانتینر روت
        } else {
            banner.visibility = View.VISIBLE
            banner.text = text
        }
    }

    fun hideOfflineBanner(activity: Activity) {
        val root = activity.findViewById<ViewGroup>(android.R.id.content)
        val banner = root.findViewById<View>(998877)
        banner?.visibility = View.GONE
    }

    // متد مرجع و مرکزی برای اجرای امن کوئری‌های GET همراه لایه کش سبک SharedPreferences
    suspend fun <T> execute(
        context: Context,
        cacheKey: String,
        type: Type,
        networkCall: suspend () -> T,
        onSuccess: (T, Boolean, Long) -> Unit,
        onFailure: (Exception) -> Unit
    ) {
        val activity = context as? Activity
        if (activity != null) {
            withContext(Dispatchers.Main) {
                showShimmer(activity)
            }
        }

        try {
            val data = withContext(Dispatchers.IO) { networkCall() }
            val json = Gson().toJson(data)
            // FIX: Bugs 19/20 - keep cache file IO off the UI thread and inside the caller's cancellable job.
            withContext(Dispatchers.IO) { CacheManager.save(context, cacheKey, json) }
            
            withContext(Dispatchers.Main) {
                if (activity != null) {
                    hideShimmer(activity)
                }
                onSuccess(data, false, System.currentTimeMillis())
            }
        } catch (e: Exception) {
            // FIX: Bugs 19/21 - cancelled search/screen work must never fall back to cache or notify the UI.
            if (e is kotlinx.coroutines.CancellationException) throw e
            // در صورت بروز هرگونه خطای شبکه، لود از روی کش محلی قبلی
            // FIX: Bug 20 - CacheManager now rejects entries older than five minutes.
            val (cachedJson, timestamp) = withContext(Dispatchers.IO) { CacheManager.get(context, cacheKey) }
            withContext(Dispatchers.Main) {
                if (activity != null) {
                    hideShimmer(activity)
                }
                if (!cachedJson.isNullOrEmpty()) {
                    try {
                        val data: T = Gson().fromJson(cachedJson, type)
                        onSuccess(data, true, timestamp)
                    } catch (parseEx: Exception) {
                        // FIX: Bugs 19/21 - callback cancellation is not a cache parsing failure either.
                        if (parseEx is kotlinx.coroutines.CancellationException) throw parseEx
                        onFailure(e)
                    }
                } else {
                    onFailure(e)
                }
            }
        }
    }
}
