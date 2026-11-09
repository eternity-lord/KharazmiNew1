package com.example.kharazmiadmin

import android.os.Bundle
import android.content.Context
import android.content.Intent
import android.view.LayoutInflater
import android.view.View
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.lifecycle.lifecycleScope
import com.google.android.material.textfield.TextInputEditText
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withTimeoutOrNull
import kotlinx.coroutines.withContext
import retrofit2.http.Body
import retrofit2.http.POST

// ==========================================
// 1. مدل‌ها و API برای تغییر رمز و تغییر شماره همراه
// ==========================================

data class ChangeMobileRequest(
    val current_mobile: String,
    val password: String,
    val new_mobile: String
)

interface SettingsApi {
    @POST("auth/change-password")
    suspend fun changePassword(@Body req: ChangePasswordRequest): SimpleResponse

    @POST("auth/change-mobile")
    suspend fun changeMobile(@Body req: ChangeMobileRequest): SimpleResponse
}

// ==========================================
// 2. کلاس اصلی اکتیویتی
// ==========================================
class SettingsActivity : BaseActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_settings)

        val credsPrefs = getSharedPreferences("UserCreds", Context.MODE_PRIVATE)
        val userSubRole = credsPrefs.getString("USER_SUB_ROLE", "admin") ?: "admin"

        val btnTeacherCredentials = findViewById<TextView>(R.id.btnTeacherCredentials)
        if (userSubRole == "admin") {
            btnTeacherCredentials.visibility = View.VISIBLE
            btnTeacherCredentials.setOnClickListener {
                startActivity(Intent(this, TeacherCredentialsActivity::class.java))
            }
        } else {
            btnTeacherCredentials.visibility = View.GONE
        }

        // --- دکمه تغییر رمز (آپدیت شده) ---
        findViewById<TextView>(R.id.btnChangePass).setOnClickListener {
            showChangePasswordDialog()
        }

        // --- دکمه تغییر شماره همراه ورود (جدید) ---
        findViewById<TextView>(R.id.btnChangeMobile).setOnClickListener {
            showChangeMobileDialog()
        }

        // --- دکمه درباره ما (با متن اختصاصی شما) ---
        findViewById<TextView>(R.id.btnAbout).setOnClickListener {
            AlertDialog.Builder(this)
                .setTitle(getString(R.string.set_about_title))
                .setMessage(getString(R.string.set_about_msg))
                .setPositiveButton(getString(R.string.common_ok), null)
                .show()
        }

        // --- دکمه خروج (همان کد شما) ---
        findViewById<TextView>(R.id.btnLogout).setOnClickListener {
            AlertDialog.Builder(this)
                .setTitle(getString(R.string.set_logout_title))
                .setMessage(getString(R.string.set_logout_msg))
                .setPositiveButton(getString(R.string.common_yes)) { _, _ ->
                    // O-03: نشست و ثبت Push همین دستگاه با هم باطل می‌شوند؛ سپس توکن ورود پاک است.
                    // خروج به شبکه وابسته نیست: در خطا یا گذشت سقف ۳ ثانیه هم از اپ خارج می‌شویم.
                    lifecycleScope.launch {
                        try {
                            withTimeoutOrNull(3000) {
                                RetrofitClient.getInstance(this@SettingsActivity)
                                    .create(AuthApi::class.java)
                                    .logout(PushTokenRegistration.currentToken(this@SettingsActivity))
                            }
                        } catch (ignored: Exception) {
                        }
                        SecureLoginStore.clearToken(this@SettingsActivity)
                        finishAffinity() // بستن کامل برنامه
                    }
                }
                .setNegativeButton(getString(R.string.common_no), null)
                .show()
        }

        // --- کلیک مخفی چند مرحله‌ای روی نسخه جهت فعال‌سازی کتابخانه سیستم طراحی خوارزمی ---
        var devClickCount = 0
        findViewById<TextView>(R.id.tvAppVersion).setOnClickListener {
            devClickCount++
            if (devClickCount >= 5) {
                devClickCount = 0
                Toast.makeText(this, getString(R.string.set_dev_on), Toast.LENGTH_SHORT).show()
                startActivity(Intent(this, DesignSystemActivity::class.java))
            } else if (devClickCount >= 2) {
                Toast.makeText(this, getString(R.string.set_dev_clicks, 5 - devClickCount), Toast.LENGTH_SHORT).show()
            }
        }
    }

    // ==========================================
    // 3. توابع جدید برای تغییر رمز
    // ==========================================

    private fun showChangePasswordDialog() {
        // باز کردن لایه‌ای که قبلا ساختیم (dialog_change_password.xml)
        val view = LayoutInflater.from(this).inflate(R.layout.dialog_change_password, null)

        val etMobile = view.findViewById<TextInputEditText>(R.id.etMobile)
        val etOld = view.findViewById<TextInputEditText>(R.id.etOldPass)
        val etNew = view.findViewById<TextInputEditText>(R.id.etNewPass)

        AlertDialog.Builder(this)
            .setTitle(getString(R.string.set_pwd_title))
            .setView(view)
            .setPositiveButton(getString(R.string.set_pwd_btn)) { _, _ ->
                val mobile = etMobile.text.toString()
                val oldPass = etOld.text.toString()
                val newPass = etNew.text.toString()

                if (mobile.isNotEmpty() && oldPass.isNotEmpty() && newPass.isNotEmpty()) {
                    changePassword(mobile, oldPass, newPass)
                } else {
                    Toast.makeText(this, getString(R.string.set_fill_all), Toast.LENGTH_SHORT).show()
                }
            }
            .setNegativeButton(getString(R.string.common_cancel), null)
            .show()
    }

    private fun changePassword(mobile: String, old: String, new: String) {
        // استفاده از کلاینت هوشمند (RetrofitClient)
        val retrofit = RetrofitClient.getInstance(this)
        val api = retrofit.create(SettingsApi::class.java)

        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.

        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val req = ChangePasswordRequest(mobile, old, new)
                val response = api.changePassword(req)

                withContext(Dispatchers.Main) {
                    Toast.makeText(this@SettingsActivity, getString(R.string.common_ok_msg, response.message), Toast.LENGTH_LONG).show()
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@SettingsActivity, getString(R.string.set_pwd_wrong), Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    private fun showChangeMobileDialog() {
        val view = LayoutInflater.from(this).inflate(R.layout.dialog_change_mobile, null)

        val etMobile = view.findViewById<TextInputEditText>(R.id.etMobile)
        val etOld = view.findViewById<TextInputEditText>(R.id.etOldPass)
        val etNewMobile = view.findViewById<TextInputEditText>(R.id.etNewMobile)

        AlertDialog.Builder(this)
            .setTitle(getString(R.string.set_mobile_title))
            .setView(view)
            .setPositiveButton(getString(R.string.set_mobile_btn)) { _, _ ->
                val mobile = etMobile.text.toString()
                val oldPass = etOld.text.toString()
                val newMobile = etNewMobile.text.toString()

                if (mobile.isNotEmpty() && oldPass.isNotEmpty() && newMobile.isNotEmpty()) {
                    changeMobile(mobile, oldPass, newMobile)
                } else {
                    Toast.makeText(this, getString(R.string.set_fill_all), Toast.LENGTH_SHORT).show()
                }
            }
            .setNegativeButton(getString(R.string.common_cancel), null)
            .show()
    }

    private fun changeMobile(mobile: String, old: String, new: String) {
        val retrofit = RetrofitClient.getInstance(this)
        val api = retrofit.create(SettingsApi::class.java)

        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.

        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val req = ChangeMobileRequest(mobile, old, new)
                val response = api.changeMobile(req)

                withContext(Dispatchers.Main) {
                    Toast.makeText(this@SettingsActivity, getString(R.string.common_ok_msg, response.message), Toast.LENGTH_LONG).show()
                    
                    // پاک کردن کلمه‌های عبور محلی و توکن‌ها جهت خروج اجباری امن
                    val credsPrefs = getSharedPreferences("UserCreds", Context.MODE_PRIVATE)
                    credsPrefs.edit().clear().apply()
                    // FIX: Clear remembered encrypted credentials too after the login identity changes.
                    SecureLoginStore.clear(this@SettingsActivity)
                    
                    // هدایت خودکار کاربر به صفحه لاگین
                    val intent = Intent(this@SettingsActivity, LoginActivity::class.java)
                    intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK)
                    startActivity(intent)
                    finish()
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    if (e is retrofit2.HttpException && e.code() == 400) {
                        Toast.makeText(this@SettingsActivity, getString(R.string.set_mobile_dup), Toast.LENGTH_LONG).show()
                    } else {
                        Toast.makeText(this@SettingsActivity, getString(R.string.set_server_error), Toast.LENGTH_LONG).show()
                    }
                }
            }
        }
    }
}
