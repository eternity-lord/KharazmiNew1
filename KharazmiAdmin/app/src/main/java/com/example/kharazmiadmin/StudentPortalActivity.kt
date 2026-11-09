package com.example.kharazmiadmin

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.text.Editable
import android.text.TextWatcher
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.*
import androidx.appcompat.app.AlertDialog
import androidx.lifecycle.lifecycleScope
import com.google.android.material.button.MaterialButton
import com.google.android.material.card.MaterialCardView
import com.google.android.material.textfield.TextInputEditText
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import java.text.DecimalFormat

// API Models for Student Portal
data class StudentOtpRequest(val mobile: String)
data class StudentLoginRequest(val mobile: String, val otp: String)
data class StudentLoginResponse(
    val status: String,
    val token: String? = null,
    val student_name: String? = null
)

interface StudentPortalApi {
    @POST("auth/student/request_otp")
    suspend fun requestOtp(@Body req: StudentOtpRequest): SimpleResponse

    @POST("auth/student/login")
    suspend fun studentLogin(@Body req: StudentLoginRequest): StudentLoginResponse

    @GET("students/my_profile")
    suspend fun getStudentProfile(): ParentProfileResponse
}

class StudentPortalActivity : BaseActivity() {

    private lateinit var flipper: ViewFlipper
    private lateinit var etMobile: TextInputEditText
    private lateinit var etOtp: TextInputEditText
    private lateinit var btnRequestOtp: Button
    private lateinit var btnLoginPortal: Button
    private lateinit var llOtpContainer: View

    // Dashboard Views
    private lateinit var tvStudentName: TextView
    private lateinit var tvStudentCode: TextView
    private lateinit var tvWalletBalance: TextView
    private lateinit var tvTotalDebt: TextView

    // Accordion Links
    private lateinit var btnViewClasses: View
    private lateinit var btnViewAttendance: View
    private lateinit var btnViewGrades: View
    private lateinit var btnViewHomework: View
    private lateinit var btnViewExams: View
    private lateinit var btnViewInstallments: View
    private lateinit var btnViewNotifications: View

    private lateinit var api: StudentPortalApi
    private var studentMobile: String = ""
    private var activeStudentProfile: ParentProfileResponse? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_student_portal)

        initViews()
        setupApi()
        setupListeners()
    }

    private fun initViews() {
        flipper = findViewById(R.id.portalFlipper)
        etMobile = findViewById(R.id.etStudentMobile)
        etOtp = findViewById(R.id.etOtpCode)
        btnRequestOtp = findViewById(R.id.btnRequestOtp)
        btnLoginPortal = findViewById(R.id.btnLoginPortal)
        llOtpContainer = findViewById(R.id.llOtpContainer)

        tvStudentName = findViewById(R.id.tvStudentName)
        tvStudentCode = findViewById(R.id.tvStudentCode)
        tvWalletBalance = findViewById(R.id.tvStudentWalletBalance)
        tvTotalDebt = findViewById(R.id.tvStudentTotalDebt)

        btnViewClasses = findViewById(R.id.btnViewClasses)
        btnViewAttendance = findViewById(R.id.btnViewAttendance)
        btnViewGrades = findViewById(R.id.btnViewGrades)
        btnViewHomework = findViewById(R.id.btnViewHomework)
        btnViewExams = findViewById(R.id.btnViewExams)
        btnViewInstallments = findViewById(R.id.btnViewInstallments)
        btnViewNotifications = findViewById(R.id.btnViewNotifications)
    }

    private fun setupApi() {
        val retrofit = RetrofitClient.getInstance(this)
        api = retrofit.create(StudentPortalApi::class.java)
    }

    private fun setupListeners() {
        btnRequestOtp.setOnClickListener {
            val mobile = etMobile.text.toString().trim()
            if (mobile.length in 10..11) {
                requestOtpFromServer(mobile)
            } else {
                Toast.makeText(this, getString(R.string.portal_mobile_invalid), Toast.LENGTH_SHORT).show()
            }
        }

        btnLoginPortal.setOnClickListener {
            val otp = etOtp.text.toString().trim()
            if (otp.length == 5) {
                loginStudentWithOtp(otp)
            } else {
                Toast.makeText(this, getString(R.string.portal_code_length), Toast.LENGTH_SHORT).show()
            }
        }

        // Accordion Details Handlers
        btnViewClasses.setOnClickListener { showClassesDialog() }
        btnViewAttendance.setOnClickListener { showAttendanceDialog() }
        btnViewGrades.setOnClickListener { showGradesDialog() }
        btnViewHomework.setOnClickListener { showHomeworkDialog() }
        btnViewExams.setOnClickListener { showExamsDialog() }
        btnViewInstallments.setOnClickListener { showInstallmentsDialog() }
        btnViewNotifications.setOnClickListener { showNotificationsDialog() }
    }

    private fun requestOtpFromServer(mobile: String) {
        studentMobile = mobile
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val res = api.requestOtp(StudentOtpRequest(mobile))
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@StudentPortalActivity, getString(R.string.common_ok_msg, res.message), Toast.LENGTH_LONG).show()
                    llOtpContainer.visibility = View.VISIBLE
                    etOtp.requestFocus()
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@StudentPortalActivity, getString(R.string.sportal_not_found), Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    private fun loginStudentWithOtp(otp: String) {
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val res = api.studentLogin(StudentLoginRequest(studentMobile, otp))
                withContext(Dispatchers.Main) {
                    if (!saveStudentToken(res.token ?: "")) return@withContext
                    loadStudentDashboard()
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@StudentPortalActivity, getString(R.string.portal_code_wrong), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    // FIX M22: توکن فقط رمزشده؛ false یعنی Keystore در دسترس نیست و نباید وارد داشبورد شد.
    private fun saveStudentToken(token: String): Boolean {
        try {
            SecureLoginStore.saveToken(this, token)
        } catch (error: Exception) {
            Toast.makeText(this, getString(R.string.common_session_save_fail), Toast.LENGTH_LONG).show()
            return false
        }
        getSharedPreferences("UserCreds", Context.MODE_PRIVATE).edit()
            .putString("USER_SUB_ROLE", "student")
            .apply()
        PushTokenRegistration.refreshAndRegister(applicationContext)
        // FIX M21: توکن در هر ریکوئست تازه خوانده می‌شود؛ نیازی به reset نیست.
        RetrofitClient.getInstance(this)
        return true
    }

    private fun loadStudentDashboard() {
        setupApi()
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val profile = api.getStudentProfile()
                withContext(Dispatchers.Main) {
                    activeStudentProfile = profile
                    flipper.displayedChild = 1 // Main Dashboard State
                    
                    tvStudentName.text = getString(R.string.portal_person_name, profile.info.name)
                    tvStudentCode.text = getString(R.string.portal_national, profile.info.national_code)
                    
                    val formatter = DecimalFormat("#,###")
                    tvWalletBalance.text = getString(R.string.portal_money, formatter.format(profile.wallet.balance))
                    tvTotalDebt.text = getString(R.string.portal_money, formatter.format(profile.wallet.total_debt))
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@StudentPortalActivity, getString(R.string.sportal_profile_error), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    // Dialog details helpers
    private fun showClassesDialog() {
        val profile = activeStudentProfile ?: return
        val list = profile.classes
        val builder = AlertDialog.Builder(this)
            .setTitle(getString(R.string.sportal_title_classes))
        if (list.isEmpty()) {
            builder.setMessage(getString(R.string.portal_empty_classes))
        } else {
            builder.setItems(list.toTypedArray(), null)
        }
        builder.setPositiveButton(getString(R.string.btn_dismiss), null).show()
    }

    private fun showAttendanceDialog() {
        val profile = activeStudentProfile ?: return
        val list = profile.attendance
        val builder = AlertDialog.Builder(this)
            .setTitle(getString(R.string.sportal_title_attendance))
        if (list.isEmpty()) {
            builder.setMessage(getString(R.string.portal_empty_attendance))
        } else {
            val items = list.map { getString(R.string.common_course_status_row, it.date, it.course_title, it.status) }.toTypedArray()
            builder.setItems(items, null)
        }
        builder.setPositiveButton(getString(R.string.btn_dismiss), null).show()
    }

    private fun showGradesDialog() {
        val profile = activeStudentProfile ?: return
        val list = profile.grades
        val builder = AlertDialog.Builder(this)
            .setTitle(getString(R.string.sportal_title_grades))
        if (list.isEmpty()) {
            builder.setMessage(getString(R.string.portal_empty_grades))
        } else {
            val items = list.map { getString(R.string.portal_grade_row, it.course_name, it.exam_title, it.score, it.max_score) }.toTypedArray()
            builder.setItems(items, null)
        }
        builder.setPositiveButton(getString(R.string.btn_dismiss), null).show()
    }

    private fun showHomeworkDialog() {
        val profile = activeStudentProfile ?: return
        val list = profile.homework
        val builder = AlertDialog.Builder(this)
            .setTitle(getString(R.string.sportal_title_homework))
        if (list.isEmpty()) {
            builder.setMessage(getString(R.string.portal_empty_homework))
        } else {
            val items = list.map { getString(R.string.portal_homework_row, it.course_title, it.title, it.due_date, it.status) }.toTypedArray()
            builder.setItems(items, null)
        }
        builder.setPositiveButton(getString(R.string.btn_dismiss), null).show()
    }

    private fun showExamsDialog() {
        val profile = activeStudentProfile ?: return
        val list = profile.exams
        val builder = AlertDialog.Builder(this)
            .setTitle(getString(R.string.sportal_title_exams))
        if (list.isEmpty()) {
            builder.setMessage(getString(R.string.portal_empty_exams))
        } else {
            val items = list.map { getString(R.string.portal_exam_row, it.course_title, it.title, it.date, it.max_score) }.toTypedArray()
            builder.setItems(items, null)
        }
        builder.setPositiveButton(getString(R.string.btn_dismiss), null).show()
    }

    private fun showInstallmentsDialog() {
        val profile = activeStudentProfile ?: return
        val list = profile.installments
        val builder = AlertDialog.Builder(this)
            .setTitle(getString(R.string.sportal_title_installments))
        if (list.isEmpty()) {
            builder.setMessage(getString(R.string.portal_empty_installments))
        } else {
            val formatter = DecimalFormat("#,###")
            val items = list.map { getString(R.string.portal_installment_row, it.course_title, formatter.format(it.amount), it.due_date, it.status) }.toTypedArray()
            builder.setItems(items, null)
        }
        builder.setPositiveButton(getString(R.string.btn_dismiss), null).show()
    }

    private fun showNotificationsDialog() {
        val profile = activeStudentProfile ?: return
        val list = profile.notifications
        val builder = AlertDialog.Builder(this)
            .setTitle(getString(R.string.sportal_title_notices))
        if (list.isEmpty()) {
            builder.setMessage(getString(R.string.portal_empty_notices))
        } else {
            val items = list.map { getString(R.string.common_announce_row, it.title, it.date, it.body) }.toTypedArray()
            builder.setItems(items, null)
        }
        builder.setPositiveButton(getString(R.string.btn_dismiss), null).show()
    }
}
