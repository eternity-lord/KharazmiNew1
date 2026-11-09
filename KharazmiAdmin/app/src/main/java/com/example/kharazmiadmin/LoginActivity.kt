package com.example.kharazmiadmin

import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.os.Bundle
import android.view.LayoutInflater
import android.widget.Button
import android.widget.CheckBox
import android.widget.EditText
import android.widget.ImageView
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.lifecycle.lifecycleScope
import androidx.biometric.BiometricPrompt
import androidx.core.content.ContextCompat
import com.google.android.material.textfield.TextInputEditText
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import retrofit2.http.Body
import retrofit2.http.POST
import retrofit2.http.Query
import java.util.concurrent.Executor

// ==========================================
// Models (Preserved/Restored based on context)
// ==========================================
// Note: Assuming these are usually in AppModels.kt, but defined here to ensure compilation based on your snippet.


interface AuthApi {
    @POST("auth/login")
    suspend fun login(@Body req: LoginRequest): LoginResponse

    // O-03: خروج سروری؛ توکن FCM اختیاری است تا فقط ثبت همین دستگاه هم‌زمان پاک شود.
    @POST("auth/logout")
    suspend fun logout(@Query("device_token") deviceToken: String? = null)
}

class LoginActivity : BaseActivity() {

    // UI Components
    private lateinit var etMobile: TextInputEditText
    private lateinit var etPass: TextInputEditText
    private lateinit var btnLogin: Button
    private lateinit var cbRemember: CheckBox
    private lateinit var btnSettings: ImageView
    private lateinit var tvRegisterLink: TextView

    // Biometric & Storage
    private lateinit var sharedPrefs: SharedPreferences
    // FIX: Android credential leftover - only remembered credentials use encrypted preferences.
    private var securePrefs: SharedPreferences? = null
    private lateinit var executor: Executor
    private lateinit var biometricPrompt: BiometricPrompt
    private lateinit var promptInfo: BiometricPrompt.PromptInfo

    override fun onCreate(savedInstanceState: Bundle?) {
        // FIX: The starting window shows the Gold logo; normal login keeps the existing application theme.
        setTheme(R.style.Theme_GajAdmin)
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_login)

        // Init Views
        etMobile = findViewById(R.id.etMobile)
        etPass = findViewById(R.id.etPassword)
        btnLogin = findViewById(R.id.btnLogin)
        cbRemember = findViewById(R.id.cbRememberMe)
        btnSettings = findViewById(R.id.btnIpSettings)
        tvRegisterLink = findViewById(R.id.tvRegisterLink)

        // Init SharedPreferences
        sharedPrefs = getSharedPreferences("UserCreds", Context.MODE_PRIVATE)
        // FIX: Migrate old plaintext passwords; if Keystore is unavailable, allow manual login without saving secrets.
        securePrefs = try {
            SecureLoginStore.open(this)
        } catch (error: Exception) {
            sharedPrefs.edit().remove("SAVED_PASS").commit()
            Toast.makeText(this, getString(R.string.login_secure_store_unavailable), Toast.LENGTH_LONG).show()
            null
        }

        // 1. Setup Biometric Logic
        setupBiometric()

        // 2. Check for saved credentials -> Trigger Biometric if exists
        checkAndTriggerBiometric()

        // Click Listener: Login Button
        btnLogin.setOnClickListener {
            val mobile = etMobile.text.toString()
            val pass = etPass.text.toString()

            if (mobile.isEmpty()) {
                Toast.makeText(this, getString(R.string.login_mobile_empty), Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }

            doLogin(mobile, pass)
        }

        // Click Listener: Parent Portal Entry
        findViewById<Button>(R.id.btnParentPortal).setOnClickListener {
            startActivity(Intent(this, ParentPortalActivity::class.java))
        }

        // Click Listener: Student Portal Entry
        findViewById<Button>(R.id.btnStudentPortal).setOnClickListener {
            startActivity(Intent(this, StudentPortalActivity::class.java))
        }

        // Click Listener: Register
        tvRegisterLink.setOnClickListener {
            val intent = Intent(this, TeacherRegisterActivity::class.java)
            startActivity(intent)
        }

        // Click Listener: Settings
        btnSettings.setOnClickListener {
            showIpDialog()
        }
    }

    // ==========================================
    // Biometric Logic
    // ==========================================
    private fun setupBiometric() {
        executor = ContextCompat.getMainExecutor(this)

        biometricPrompt = BiometricPrompt(this, executor, object : BiometricPrompt.AuthenticationCallback() {
            override fun onAuthenticationError(errorCode: Int, errString: CharSequence) {
                super.onAuthenticationError(errorCode, errString)
                // If user cancels or hardware error, we just let them use manual login.
                // We only show toast if it's not a user cancellation (to be less annoying).
                if (errorCode != BiometricPrompt.ERROR_NEGATIVE_BUTTON && errorCode != BiometricPrompt.ERROR_USER_CANCELED) {
                    Toast.makeText(this@LoginActivity, getString(R.string.login_biometric_error, errString), Toast.LENGTH_SHORT).show()
                }
            }

            override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
                super.onAuthenticationSucceeded(result)
                // Retrieve credentials
                // FIX: Never read a remembered password from the ordinary session preferences.
                val (savedMobile, savedPass) = readRememberedCredentials()

                if (savedMobile.isNotEmpty() && savedPass.isNotEmpty()) {
                    // Auto-fill and Login
                    etMobile.setText(savedMobile)
                    etPass.setText(savedPass)
                    // FIX L10: ورود بیومتریک یعنی تمایل به ماندنِ remember — وگرنه همین لاگین موفق، ذخیره را پاک می‌کرد.
                    cbRemember.isChecked = true
                    Toast.makeText(this@LoginActivity, getString(R.string.login_biometric_success), Toast.LENGTH_SHORT).show()
                    doLogin(savedMobile, savedPass)
                }
            }

            override fun onAuthenticationFailed() {
                super.onAuthenticationFailed()
                Toast.makeText(this@LoginActivity, getString(R.string.login_biometric_failed), Toast.LENGTH_SHORT).show()
            }
        })

        promptInfo = BiometricPrompt.PromptInfo.Builder()
            .setTitle(getString(R.string.login_biometric_title))
            .setSubtitle(getString(R.string.login_biometric_subtitle))
            .setNegativeButtonText(getString(R.string.login_biometric_use_password))
            .build()
    }

    // FIX: A corrupt/inaccessible encrypted entry must not crash login or trigger an insecure fallback.
    private fun readRememberedCredentials(): Pair<String, String> = try {
        Pair(securePrefs?.getString("SAVED_MOBILE", "") ?: "", securePrefs?.getString("SAVED_PASS", "") ?: "")
    } catch (error: Exception) {
        securePrefs = null
        Toast.makeText(this, getString(R.string.login_secure_read_failed), Toast.LENGTH_LONG).show()
        Pair("", "")
    }

    private fun checkAndTriggerBiometric() {
        // FIX: No biometric auto-login unless encrypted credentials are available.
        val (savedMobile, savedPass) = readRememberedCredentials()

        if (!savedMobile.isNullOrEmpty() && !savedPass.isNullOrEmpty()) {
            biometricPrompt.authenticate(promptInfo)
        }
    }

    // ==========================================
    // Existing Logic (Modified to Save Creds)
    // ==========================================
    private fun showIpDialog() {
        val view = LayoutInflater.from(this).inflate(R.layout.dialog_ip_input, null)
        val etIp = view.findViewById<EditText>(R.id.etIpInput)

        val prefs = getSharedPreferences("AppConfig", Context.MODE_PRIVATE)
        // FIX: Prefer a TLS endpoint in server configuration too.
        etIp.setText(prefs.getString("SERVER_IP", ServerAddress.DEFAULT_ADDRESS))

        AlertDialog.Builder(this)
            .setTitle(getString(R.string.login_server_title))
            // FIX: Make the insecure local compatibility option explicit before credentials are sent.
            .setMessage(getString(R.string.login_server_message))
            .setView(view)
            .setPositiveButton(getString(R.string.action_save)) { _, _ ->
                val newIp = etIp.text.toString().trim()
                if (newIp.isNotEmpty()) {
                    // FIX: Reject malformed server addresses without crashing the configuration screen.
                    try {
                        RetrofitClient.saveIp(this, newIp)
                        Toast.makeText(this, getString(R.string.login_server_saved), Toast.LENGTH_SHORT).show()
                    } catch (error: Exception) {
                        Toast.makeText(this, getString(R.string.login_server_invalid), Toast.LENGTH_LONG).show()
                    }
                }
            }
            .setNegativeButton(getString(R.string.common_cancel), null)
            .show()
    }

    private fun doLogin(mobile: String, pass: String) {
        val retrofit = RetrofitClient.getInstance(this)
        val api = retrofit.create(AuthApi::class.java)

        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.

        // FIX: Show loading on the existing button, without changing the request.
        (btnLogin as? GoldButton)?.setLoading(true)
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val response = api.login(LoginRequest(mobile, if(pass.isEmpty()) null else pass))

                withContext(Dispatchers.Main) {
                    // FIX: Restore the button on both success and failure.
                    (btnLogin as? GoldButton)?.setLoading(false)
                    // FIX L10: ذخیره‌ی رمز فقط با تیک «مرا به خاطر بسپار»؛ بدون تیک، بقایای قبلی هم پاک می‌شود.
                    if (cbRemember.isChecked) {
                        // FIX: Password persistence is encrypted and optional; never fall back to plaintext after failure.
                        try {
                            val stored = securePrefs?.edit()
                                ?.putString("SAVED_MOBILE", mobile)
                                ?.putString("SAVED_PASS", pass)
                                ?.commit() ?: false
                            if (!stored) Toast.makeText(this@LoginActivity, getString(R.string.login_quick_save_failed), Toast.LENGTH_LONG).show()
                        } catch (error: Exception) {
                            // FIX: Bug 19 - preserve cancellation even during optional credential persistence.
                            if (error is kotlinx.coroutines.CancellationException) throw error
                            Toast.makeText(this@LoginActivity, getString(R.string.login_password_store_unavailable), Toast.LENGTH_LONG).show()
                        }
                    } else {
                        try {
                            securePrefs?.edit()?.remove("SAVED_MOBILE")?.remove("SAVED_PASS")?.apply()
                        } catch (ignored: Exception) {
                        }
                    }
                    // FIX M22: توکن سشن فقط رمزشده؛ شکست یعنی نماندن در حالت «نیمه‌لاگین» — روی لاگین می‌مانیم.
                    try {
                        SecureLoginStore.saveToken(this@LoginActivity, response.token ?: "")
                    } catch (error: Exception) {
                        Toast.makeText(this@LoginActivity, getString(R.string.common_session_save_fail), Toast.LENGTH_LONG).show()
                        return@withContext
                    }
                    // FIX M22: فقط نقش/شعبه (غیرمحرمانه) در UserCreds؛ توکن در SecureLoginStore است.
                    sharedPrefs.edit().apply {
                        putString("SAVED_MOBILE", mobile)
                        remove("SAVED_PASS") // FIX: remove any remaining legacy plaintext password.
                        remove("USER_TOKEN") // FIX M22: پاک‌سازی بقایای احتمالی توکن plaintext قدیمی.
                        putString("USER_ROLE", response.role)
                        putString("USER_SUB_ROLE", response.sub_role ?: "admin")
                        putInt("USER_BRANCH_ID", response.branch_id ?: 1)
                        apply()
                    }
                    PushTokenRegistration.refreshAndRegister(applicationContext)
                    // ----------------------------------------

                    Toast.makeText(this@LoginActivity, getString(R.string.common_ok_msg, response.message), Toast.LENGTH_SHORT).show()

                    if (response.role == "admin") {
                        val intent = Intent(this@LoginActivity, MainActivity::class.java)
                        startActivity(intent)
                        finish()
                    } else if (response.role == "teacher") {
                        val intent = Intent(this@LoginActivity, TeacherDashboardActivity::class.java)
                        intent.putExtra("TEACHER_ID", response.user_id)
                        intent.putExtra("TEACHER_NAME", response.name)
                        startActivity(intent)
                        finish()
                    }
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                // FIX M23 (مثل C10): باز کردن catch — هر خطا پیام خودش را دارد، نه «رمز اشتباه» برای همه.
                val msg = when {
                    e is retrofit2.HttpException && e.code() == 429 ->
                        getString(R.string.login_error_rate_limit)
                    e is retrofit2.HttpException && e.code() == 403 ->
                        getString(R.string.login_error_suspended)
                    e is retrofit2.HttpException && e.code() == 404 ->
                        getString(R.string.login_error_user_not_found)
                    e is retrofit2.HttpException && e.code() == 400 ->
                        getString(R.string.login_error_wrong_credentials)
                    e is java.io.IOException ->
                        getString(R.string.login_error_connection)
                    e is retrofit2.HttpException ->
                        getString(R.string.login_error_server_code, e.code())
                    else -> getString(R.string.login_error_unexpected)
                }
                withContext(Dispatchers.Main) {
                    // FIX: Restore the button on both success and failure.
                    (btnLogin as? GoldButton)?.setLoading(false)
                    Toast.makeText(this@LoginActivity, msg, Toast.LENGTH_LONG).show()
                    android.util.Log.e("LoginActivity", "doLogin failed", e)
                }
            }
        }
    }
}
