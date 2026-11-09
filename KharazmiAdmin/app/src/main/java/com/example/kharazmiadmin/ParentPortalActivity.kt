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
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
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

// API Models for Parent Portal
data class ParentOtpRequest(val mobile: String)

data class ParentLoginResponse(
    val status: String,
    val multiple_children: Boolean,
    val token: String? = null,
    val temp_token: String? = null,
    val student_name: String? = null,
    val children: List<ParentSimpleStudentItem>? = null
)

data class ParentSimpleStudentItem(
    val id: Int,
    val name: String
)

data class ParentLoginRequest(val mobile: String, val otp: String)
data class ChildSelectRequest(val temp_token: String, val student_id: Int)

data class ParentProfileResponse(
    val info: ParentStudentInfo,
    val classes: List<String>,
    val wallet: ParentWalletInfo,
    val grades: List<ParentGradeItem>,
    val attendance: List<ParentAttendanceItem>,
    val installments: List<ParentInstallmentItem>,
    val homework: List<ParentHomeworkItem>,
    val exams: List<ParentExamItem>,
    val upcoming_sessions: List<ParentUpcomingSessionItem>,
    val notifications: List<ParentNotificationItem>
)

data class ParentStudentInfo(val name: String, val national_code: String, val parent_mobile: String, val profile_image: String?)
data class ParentWalletInfo(val balance: Long, val total_debt: Long)
data class ParentGradeItem(val course_name: String, val exam_title: String, val score: Float, val max_score: Float, val date: String, val description: String?)
data class ParentAttendanceItem(val date: String, val course_title: String, val status: String)
data class ParentInstallmentItem(val course_title: String, val amount: Long, val due_date: String, val is_paid: Boolean, val status: String, val paid_at: String)
data class ParentHomeworkItem(val course_title: String, val title: String, val due_date: String, val status: String)
data class ParentExamItem(val course_title: String, val title: String, val date: String, val max_score: Float)
data class ParentUpcomingSessionItem(val course_title: String, val date: String, val time: String)
data class ParentNotificationItem(val title: String, val body: String, val date: String)

interface ParentPortalApi {
    @POST("parent/request_otp")
    suspend fun requestOtp(@Body req: ParentOtpRequest): SimpleResponse

    @POST("parent/login")
    suspend fun parentLogin(@Body req: ParentLoginRequest): ParentLoginResponse

    @POST("parent/select_child")
    suspend fun selectChild(@Body req: ChildSelectRequest): ParentLoginResponse

    @GET("parent/child_profile")
    suspend fun getChildProfile(): ParentProfileResponse
}

class ParentPortalActivity : BaseActivity() {

    private lateinit var flipper: ViewFlipper
    private lateinit var etMobile: TextInputEditText
    private lateinit var etOtp: TextInputEditText
    private lateinit var btnRequestOtp: Button
    private lateinit var btnLoginPortal: Button
    private lateinit var llOtpContainer: View
    private lateinit var rvChildren: RecyclerView

    // Dashboard Views
    private lateinit var tvChildName: TextView
    private lateinit var tvChildCode: TextView
    private lateinit var btnSwitchChild: Button
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

    private lateinit var api: ParentPortalApi
    private var parentMobile: String = ""
    private var tempToken: String = ""
    private var activeChildProfile: ParentProfileResponse? = null
    private var multipleChildrenList: List<ParentSimpleStudentItem> = emptyList()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_parent_portal)

        initViews()
        setupApi()
        setupListeners()
    }

    private fun initViews() {
        flipper = findViewById(R.id.portalFlipper)
        etMobile = findViewById(R.id.etParentMobile)
        etOtp = findViewById(R.id.etOtpCode)
        btnRequestOtp = findViewById(R.id.btnRequestOtp)
        btnLoginPortal = findViewById(R.id.btnLoginPortal)
        llOtpContainer = findViewById(R.id.llOtpContainer)
        rvChildren = findViewById(R.id.rvChildren)

        tvChildName = findViewById(R.id.tvChildName)
        tvChildCode = findViewById(R.id.tvChildCode)
        btnSwitchChild = findViewById(R.id.btnSwitchChild)
        tvWalletBalance = findViewById(R.id.tvParentWalletBalance)
        tvTotalDebt = findViewById(R.id.tvParentTotalDebt)

        btnViewClasses = findViewById(R.id.btnViewClasses)
        btnViewAttendance = findViewById(R.id.btnViewAttendance)
        btnViewGrades = findViewById(R.id.btnViewGrades)
        btnViewHomework = findViewById(R.id.btnViewHomework)
        btnViewExams = findViewById(R.id.btnViewExams)
        btnViewInstallments = findViewById(R.id.btnViewInstallments)
        btnViewNotifications = findViewById(R.id.btnViewNotifications)

        rvChildren.layoutManager = LinearLayoutManager(this)
    }

    private fun setupApi() {
        val retrofit = RetrofitClient.getInstance(this)
        api = retrofit.create(ParentPortalApi::class.java)
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
                loginParentWithOtp(otp)
            } else {
                Toast.makeText(this, getString(R.string.portal_code_length), Toast.LENGTH_SHORT).show()
            }
        }

        btnSwitchChild.setOnClickListener {
            if (multipleChildrenList.isNotEmpty()) {
                flipper.displayedChild = 1 // Switch back to Child Selection
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
        parentMobile = mobile
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val res = api.requestOtp(ParentOtpRequest(mobile))
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@ParentPortalActivity, getString(R.string.common_ok_msg, res.message), Toast.LENGTH_LONG).show()
                    llOtpContainer.visibility = View.VISIBLE
                    etOtp.requestFocus()
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@ParentPortalActivity, getString(R.string.pportal_not_registered), Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    private fun loginParentWithOtp(otp: String) {
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val res = api.parentLogin(ParentLoginRequest(parentMobile, otp))
                withContext(Dispatchers.Main) {
                    if (res.multiple_children) {
                        tempToken = res.temp_token ?: ""
                        multipleChildrenList = res.children ?: emptyList()
                        flipper.displayedChild = 1 // Child Selection State
                        bindChildrenList()
                    } else {
                        // Single Child Flow -> Save Token and go to Dashboard
                        val token = res.token ?: ""
                        if (!saveParentToken(token)) return@withContext
                        loadParentDashboard()
                    }
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@ParentPortalActivity, getString(R.string.portal_code_wrong), Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    private fun bindChildrenList() {
        btnSwitchChild.visibility = View.VISIBLE
        rvChildren.adapter = ChildrenAdapter(multipleChildrenList) { child ->
            selectChildAndGoToDashboard(child.id)
        }
    }

    private fun selectChildAndGoToDashboard(studentId: Int) {
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val res = api.selectChild(ChildSelectRequest(tempToken, studentId))
                withContext(Dispatchers.Main) {
                    if (!saveParentToken(res.token ?: "")) return@withContext
                    loadParentDashboard()
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@ParentPortalActivity, getString(R.string.pportal_child_error), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    // FIX M22: توکن فقط رمزشده؛ false یعنی Keystore در دسترس نیست و نباید وارد داشبورد شد.
    private fun saveParentToken(token: String): Boolean {
        try {
            SecureLoginStore.saveToken(this, token)
        } catch (error: Exception) {
            Toast.makeText(this, getString(R.string.common_session_save_fail), Toast.LENGTH_LONG).show()
            return false
        }
        getSharedPreferences("UserCreds", Context.MODE_PRIVATE).edit()
            .putString("USER_SUB_ROLE", "parent")
            .apply()
        PushTokenRegistration.refreshAndRegister(applicationContext)
        // FIX M21: توکن در هر ریکوئست تازه خوانده می‌شود؛ نیازی به reset نیست.
        RetrofitClient.getInstance(this)
        return true
    }

    private fun loadParentDashboard() {
        // We recheck API instance because RetrofitClient instance changed after saving new token
        setupApi()
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val profile = api.getChildProfile()
                withContext(Dispatchers.Main) {
                    activeChildProfile = profile
                    flipper.displayedChild = 2 // Main Dashboard State
                    
                    tvChildName.text = getString(R.string.portal_person_name, profile.info.name)
                    tvChildCode.text = getString(R.string.portal_national, profile.info.national_code)
                    
                    val formatter = DecimalFormat("#,###")
                    tvWalletBalance.text = getString(R.string.portal_money, formatter.format(profile.wallet.balance))
                    tvTotalDebt.text = getString(R.string.portal_money, formatter.format(profile.wallet.total_debt))
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@ParentPortalActivity, getString(R.string.pportal_balance_error), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    // Dialog details helpers
    private fun showClassesDialog() {
        val profile = activeChildProfile ?: return
        val list = profile.classes
        val builder = AlertDialog.Builder(this)
            .setTitle(getString(R.string.pportal_title_classes))
        if (list.isEmpty()) {
            builder.setMessage(getString(R.string.portal_empty_classes))
        } else {
            builder.setItems(list.toTypedArray(), null)
        }
        builder.setPositiveButton(getString(R.string.btn_dismiss), null).show()
    }

    private fun showAttendanceDialog() {
        val profile = activeChildProfile ?: return
        val list = profile.attendance
        val builder = AlertDialog.Builder(this)
            .setTitle(getString(R.string.pportal_title_attendance))
        if (list.isEmpty()) {
            builder.setMessage(getString(R.string.portal_empty_attendance))
        } else {
            val items = list.map { getString(R.string.common_course_status_row, it.date, it.course_title, it.status) }.toTypedArray()
            builder.setItems(items, null)
        }
        builder.setPositiveButton(getString(R.string.btn_dismiss), null).show()
    }

    private fun showGradesDialog() {
        val profile = activeChildProfile ?: return
        val list = profile.grades
        val builder = AlertDialog.Builder(this)
            .setTitle(getString(R.string.pportal_title_grades))
        if (list.isEmpty()) {
            builder.setMessage(getString(R.string.portal_empty_grades))
        } else {
            val items = list.map { getString(R.string.portal_grade_row, it.course_name, it.exam_title, it.score, it.max_score) }.toTypedArray()
            builder.setItems(items, null)
        }
        builder.setPositiveButton(getString(R.string.btn_dismiss), null).show()
    }

    private fun showHomeworkDialog() {
        val profile = activeChildProfile ?: return
        val list = profile.homework
        val builder = AlertDialog.Builder(this)
            .setTitle(getString(R.string.pportal_title_homework))
        if (list.isEmpty()) {
            builder.setMessage(getString(R.string.portal_empty_homework))
        } else {
            val items = list.map { getString(R.string.portal_homework_row, it.course_title, it.title, it.due_date, it.status) }.toTypedArray()
            builder.setItems(items, null)
        }
        builder.setPositiveButton(getString(R.string.btn_dismiss), null).show()
    }

    private fun showExamsDialog() {
        val profile = activeChildProfile ?: return
        val list = profile.exams
        val builder = AlertDialog.Builder(this)
            .setTitle(getString(R.string.pportal_title_exams))
        if (list.isEmpty()) {
            builder.setMessage(getString(R.string.portal_empty_exams))
        } else {
            val items = list.map { getString(R.string.portal_exam_row, it.course_title, it.title, it.date, it.max_score) }.toTypedArray()
            builder.setItems(items, null)
        }
        builder.setPositiveButton(getString(R.string.btn_dismiss), null).show()
    }

    private fun showInstallmentsDialog() {
        val profile = activeChildProfile ?: return
        val list = profile.installments
        val builder = AlertDialog.Builder(this)
            .setTitle(getString(R.string.pportal_title_installments))
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
        val profile = activeChildProfile ?: return
        val list = profile.notifications
        val builder = AlertDialog.Builder(this)
            .setTitle(getString(R.string.pportal_title_notices))
        if (list.isEmpty()) {
            builder.setMessage(getString(R.string.portal_empty_notices))
        } else {
            val items = list.map { getString(R.string.common_announce_row, it.title, it.date, it.body) }.toTypedArray()
            builder.setItems(items, null)
        }
        builder.setPositiveButton(getString(R.string.btn_dismiss), null).show()
    }
}

class ChildrenAdapter(
    private val list: List<ParentSimpleStudentItem>,
    private val onClick: (ParentSimpleStudentItem) -> Unit
) : RecyclerView.Adapter<ChildrenAdapter.VH>() {

    class VH(v: View) : RecyclerView.ViewHolder(v) {
        val title: TextView = v.findViewById(android.R.id.text1)
        val subtitle: TextView = v.findViewById(android.R.id.text2)
        init {
            subtitle.textSize = 12f
            subtitle.setTextColor(UiColors.resolve(v.context, R.color.text_secondary))
        }
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val v = LayoutInflater.from(parent.context).inflate(android.R.layout.simple_list_item_2, parent, false)
        return VH(v)
    }

    override fun onBindViewHolder(holder: VH, position: Int) {
        val item = list[position]
        holder.title.text = holder.itemView.context.getString(R.string.common_person_row, item.name)
        holder.subtitle.text = holder.itemView.context.getString(R.string.pportal_child_hint)
        holder.itemView.setOnClickListener { onClick(item) }
    }

    override fun getItemCount() = list.size
}
