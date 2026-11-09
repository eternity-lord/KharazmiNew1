package com.example.kharazmiadmin

import android.content.Context
import android.os.Handler
import android.os.Looper
import android.widget.Toast
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory

object RetrofitClient {

    // FIX: Prefer HTTPS by default; explicit HTTP remains a warned local compatibility option.
    @Volatile private var warnedHttpUrl: String? = null

    // FIX M21: تک‌نمونه در طول عمر اپ — OkHttpClient فقط یک‌بار ساخته و reuse می‌شود؛
    // Retrofit هم به‌ازای هر baseUrl کش می‌شود (آدرس سرور با saveIp عوض‌شدنی است و نباید فریز شود).
    // اینترسپتور فقط applicationContext نگه می‌دارد تا Activity در کشِ سراسری لیک نشود.
    @Volatile private var cachedClient: OkHttpClient? = null
    @Volatile private var cachedBaseUrl: String? = null
    @Volatile private var cachedRetrofit: Retrofit? = null

    private fun warnIfInsecure(context: Context, url: String) {
        if (url.startsWith("http://") && warnedHttpUrl != url) {
            warnedHttpUrl = url
            android.util.Log.w("RetrofitClient", "HTTP server configured: traffic is not encrypted")
            Handler(Looper.getMainLooper()).post {
                Toast.makeText(context.applicationContext, context.getString(R.string.rcli_http_warn), Toast.LENGTH_LONG).show()
            }
        }
    }

    private fun getBaseUrl(context: Context): String {
        val prefs = context.getSharedPreferences("AppConfig", Context.MODE_PRIVATE)
        val saved = prefs.getString("SERVER_IP", ServerAddress.DEFAULT_ADDRESS) ?: ServerAddress.DEFAULT_ADDRESS
        val url = try {
            ServerAddress.normalize(saved)
        } catch (error: Exception) {
            // FIX: A malformed old setting must not crash every Activity that constructs Retrofit.
            Handler(Looper.getMainLooper()).post {
                Toast.makeText(context.applicationContext, context.getString(R.string.rcli_addr_invalid), Toast.LENGTH_LONG).show()
            }
            ServerAddress.DEFAULT_ADDRESS
        }
        warnIfInsecure(context, url)
        return url
    }

    // ذخیره آدرس جدید
    fun saveIp(context: Context, ip: String) {
        val prefs = context.getSharedPreferences("AppConfig", Context.MODE_PRIVATE)
        // FIX: Validate once, prefer TLS for bare hosts and warn immediately if HTTP was explicitly selected.
        val url = ServerAddress.normalize(ip)
        prefs.edit().putString("SERVER_IP", url).apply()
        // FIX M21: عوض شدن آدرس، کش Retrofit را باطل می‌کند (کلید کش همان URL است؛ این صراحت است).
        cachedBaseUrl = null
        cachedRetrofit = null
        warnIfInsecure(context, url)
    }

    // FIX M21: ساخت یک‌باره‌ی OkHttpClient — منطق اینترسپتور (توکن/401/403) عین قبل است.
    private fun buildClient(appContext: Context): OkHttpClient {
        return OkHttpClient.Builder()
            // FIX: Do not silently follow redirects that downgrade HTTPS to cleartext HTTP.
            .followSslRedirects(false)
            .addInterceptor { chain ->
                val request = chain.request()
                
                // دریافت خودکار توکن امنیت کاربر و تزریق آن به عنوان هدر سراسری Authorization
                // FIX M22: خواندن توکن از حافظه‌ی رمزشده (نمونه‌ی کش‌شده؛ بدون MasterKeyسازی در هر ریکوئست).
                val token = SecureLoginStore.getToken(appContext)
                
                val requestBuilder = request.newBuilder()
                if (token.isNotEmpty()) {
                    requestBuilder.addHeader("Authorization", "Bearer $token")
                }
                
                val newRequest = requestBuilder.build()
                val response = chain.proceed(newRequest)
                
                // مدیریت خودکار خطای ۴۰۱ (انقضای سشن)
                // FIX M30: بدون ناوبری مستقیم از اینترسپتور — فقط فلگ + Toast کوتاه؛
                // دیالوگ «ورود مجدد» در onResume هاست (BaseActivity) نشان داده می‌شود تا فرم پرشده گم نشود.
                if (response.code() == 401) {
                    SessionExpiry.signal()
                    SecureLoginStore.clearToken(appContext)
                    Handler(Looper.getMainLooper()).post {
                        Toast.makeText(appContext, appContext.getString(R.string.rcli_session_exp), Toast.LENGTH_SHORT).show()
                    }
                }
                
                // مدیریت خودکار خطای ۴۰۳ (عدم دسترسی) کلاینت‌ساید
                if (response.code() == 403) {
                    Handler(Looper.getMainLooper()).post {
                        Toast.makeText(appContext, appContext.getString(R.string.rcli_no_access), Toast.LENGTH_LONG).show()
                    }
                }
                response
            }
            .build()
    }

    private fun getClient(appContext: Context): OkHttpClient {
        cachedClient?.let { return it }
        return synchronized(this) {
            cachedClient ?: buildClient(appContext).also { cachedClient = it }
        }
    }

    // ساختن Retrofit همراه OkHttpClient و اینترسپتور هوشمند دسترسی‌ها
    fun getInstance(context: Context): Retrofit {
        val appContext = context.applicationContext
        val baseUrl = getBaseUrl(appContext)
        val hit = cachedRetrofit
        if (hit != null && cachedBaseUrl == baseUrl) return hit
        return synchronized(this) {
            val hit2 = cachedRetrofit
            if (hit2 != null && cachedBaseUrl == baseUrl) hit2
            else {
                Retrofit.Builder()
                    .baseUrl(baseUrl)
                    .client(getClient(appContext))
                    .addConverterFactory(GsonConverterFactory.create())
                    .build()
                    .also { cachedBaseUrl = baseUrl; cachedRetrofit = it }
            }
        }
    }
}
