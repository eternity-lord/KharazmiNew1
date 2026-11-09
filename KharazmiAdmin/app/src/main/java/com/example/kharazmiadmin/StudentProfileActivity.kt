package com.example.kharazmiadmin

import android.content.Intent
import android.content.Context
import android.net.Uri
import android.os.Bundle
import android.view.View
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.google.android.material.textfield.TextInputLayout
import com.google.android.material.textfield.TextInputEditText
import com.google.android.material.card.MaterialCardView
import android.widget.AutoCompleteTextView
import android.widget.ArrayAdapter
import android.view.ViewGroup
import android.view.LayoutInflater
import com.google.android.material.button.MaterialButton
import com.google.android.material.floatingactionbutton.FloatingActionButton
import com.google.android.material.materialswitch.MaterialSwitch
import com.google.android.material.tabs.TabLayout
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.util.Locale
import kotlin.math.abs
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Path

// ==========================================
// 2. Unified Profile API (Updated)
// ==========================================
interface ProfileApi {
    // --- Student View (Full) ---
    @GET("admin/students/{id}/full_profile")
    suspend fun getFullStudentProfile(@Path("id") id: Int): FullStudentProfile

    @GET("students/{id}/grades")
    suspend fun getStudentGrades(@Path("id") id: Int): StudentGradesResponse

    @GET("students/{id}")
    suspend fun getStudentProfile(@Path("id") id: Int): StudentRawProfile

    @PUT("students/update/{id}")
    suspend fun updateStudent(@Path("id") id: Int, @Body data: StudentUpdate): SimpleResponse

    // --- Management ---
    @DELETE("admin/students/{id}")
    suspend fun deleteStudent(@Path("id") id: Int): SimpleResponse

    @POST("admin/students/{id}/toggle_suspend")
    suspend fun toggleSuspend(@Path("id") id: Int): SuspendResponse

    // --- Teacher View (Full) ---
    @GET("teachers/{id}/full_profile")
    suspend fun getFullTeacherProfile(@Path("id") id: Int): FullTeacherProfile

    @GET("teachers/{id}")
    suspend fun getTeacherProfile(@Path("id") id: Int): TeacherRawProfile

    @PUT("teachers/update/{id}") // ✅ اضافه شد برای EditTeacherActivity
    suspend fun updateTeacher(@Path("id") id: Int, @Body data: TeacherUpdate): SimpleResponse

    @retrofit2.http.Multipart
    @POST("students/{id}/upload_photo")
    suspend fun uploadStudentPhoto(
        @Path("id") id: Int,
        @retrofit2.http.Part file: okhttp3.MultipartBody.Part
    ): SimpleResponse

    @retrofit2.http.Multipart
    @POST("teachers/{id}/upload_photo")
    suspend fun uploadTeacherPhoto(
        @Path("id") id: Int,
        @retrofit2.http.Part file: okhttp3.MultipartBody.Part
    ): SimpleResponse

    @GET("teachers/{id}/pending_settlement")
    suspend fun getPendingSettlement(@Path("id") id: Int): TeacherPendingSettlementResponse

    @POST("teachers/{id}/settle")
    suspend fun settleTeacherSessions(@Path("id") id: Int, @Body req: SettleRequest): TeacherSettlementResponse

    @GET("teachers/{id}/settlement_history")
    suspend fun getSettlementHistory(@Path("id") id: Int): List<SettlementHistoryItem>

    @GET("students/{id}/installments")
    suspend fun getStudentInstallments(@Path("id") id: Int): List<StudentInstallmentItem>

    @GET("students/{id}/communication_history")
    suspend fun getStudentCommunicationHistory(
        @Path("id") id: Int
    ): List<CommunicationHistoryItem>

    @GET("teachers/{id}/communication_history")
    suspend fun getTeacherCommunicationHistory(
        @Path("id") id: Int
    ): List<CommunicationHistoryItem>

    @POST("admin/students/{id}/send_portal_link")
    suspend fun sendPortalLink(@Path("id") id: Int): SimpleResponse

    @GET("teachers/{id}/collaboration_summary")
    suspend fun getTeacherCollaborationSummary(
        @Path("id") id: Int
    ): TeacherCollaborationSummary
}

// ==========================================
// 3. Activity Logic
// ==========================================
class StudentProfileActivity : BaseActivity() {

    private var studentId: Int = -1
    // FIX (گروه۳/آیتم۱۴): این صفحه از دلِ کلاس در پنل معلم هم باز می‌شود
    // (AttendanceActivity:934 / ClassSetupActivity:505 / LiveRosterActivity:160)؛
    // برای معلم فقط خواندنی است ⇒ اکشن‌های پولی/مدیریتی پنهان و بدون listener.
    private var isTeacherUser = false
    private lateinit var tvContent: TextView
    private lateinit var tvName: TextView
    private lateinit var tvPhone: TextView
    private lateinit var tabLayout: TabLayout
    private lateinit var switchSuspend: MaterialSwitch
    private lateinit var btnInvoice: MaterialButton
    private lateinit var llStandardContainer: View
    private lateinit var llCommunicationContainer: View
    private lateinit var rvCommunicationHistory: RecyclerView
    private lateinit var tvCommunicationEmpty: TextView
    // Timeline 360
    private lateinit var llTimelineContainer: View
    private lateinit var rvTimeline: RecyclerView
    private lateinit var tvTimelineEmpty: TextView
    private var timelineAdapter: TimelineAdapter? = null

    private lateinit var tvTotalDebt: TextView
    private lateinit var tvDebtTeacher: TextView
    private lateinit var tvDebtInstitute: TextView

    // A1: اقساط — ویوهای تب اقساط (RecyclerView + دکمه افزودن)
    private lateinit var cardContent: View
    private lateinit var cardInstallments: View
    private lateinit var rvInstallments: RecyclerView
    private lateinit var tvInstallmentsEmpty: TextView
    private lateinit var btnAddInstallment: MaterialButton
    private var installmentAdapter: InstallmentAdapter? = null
    private var currentInstallments: List<StudentInstallmentItem> = emptyList()

    private var cachedProfile: FullStudentProfile? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_student_profile)

        studentId = intent.getIntExtra("STUDENT_ID", -1)
        if (studentId == -1) {
            Toast.makeText(this, getString(R.string.profile_id_error), Toast.LENGTH_SHORT).show()
            finish()
            return
        }

        initViews()

        tabLayout.addOnTabSelectedListener(object : TabLayout.OnTabSelectedListener {
            override fun onTabSelected(tab: TabLayout.Tab?) {
                when (tab?.position) {
                    0 -> {
                        showStandardProfileContent()
                        showInfo()
                    }
                    1 -> {
                        showStandardProfileContent()
                        showFinancial()
                    }
                    2 -> {
                        showStandardProfileContent()
                        fetchGrades()
                    }
                    3 -> {
                        showInstallmentsContent()
                        fetchInstallments()
                    }
                    4 -> {
                        showCommunicationContent()
                        fetchCommunicationHistory()
                    }
                    5 -> {
                        showTimelineContent()
                        fetchTimeline()
                    }
                }
            }
            override fun onTabUnselected(tab: TabLayout.Tab?) {}
            override fun onTabReselected(tab: TabLayout.Tab?) {
                if (tab?.position == 4) fetchCommunicationHistory()
                if (tab?.position == 5) fetchTimeline()
            }
        })

        if (intent.getBooleanExtra("OPEN_INSTALLMENTS_TAB", false)) {
            tabLayout.getTabAt(3)?.select()
        }

        // FIX (گروه۳/آیتم۱۴): ویرایش پروفایل برای معلم پنهان و بدون listener است
        // (isTeacherUser در initViews() مقدار می‌گیرد که پیش از اینجا صدا زده شده).
        if (!isTeacherUser) {
            findViewById<FloatingActionButton>(R.id.fabEditProfile).setOnClickListener {
                val intent = Intent(this, EditStudentActivity::class.java)
                intent.putExtra("STUDENT_ID", studentId)
                startActivity(intent)
            }
        }
    }

    override fun onResume() {
        super.onResume()
        fetchFullData()
        if (tabLayout.selectedTabPosition == 4) {
            fetchCommunicationHistory()
        }
        if (tabLayout.selectedTabPosition == 5) {
            fetchTimeline()
        }
    }

    private fun initViews() {
        tvContent = findViewById(R.id.tvContent)
        tvName = findViewById(R.id.tvProfileName)
        tvPhone = findViewById(R.id.tvProfilePhone)
        tabLayout = findViewById(R.id.tabLayoutProfile)
        switchSuspend = findViewById(R.id.switchSuspend)
        llStandardContainer = findViewById(R.id.llStudentStandardContainer)
        llCommunicationContainer = findViewById(R.id.llStudentCommunicationContainer)
        rvCommunicationHistory = findViewById(R.id.rvStudentCommunicationHistory)
        tvCommunicationEmpty = findViewById(R.id.tvStudentCommunicationEmpty)
        rvCommunicationHistory.layoutManager = LinearLayoutManager(this)
        rvCommunicationHistory.isNestedScrollingEnabled = false
        // Timeline 360
        llTimelineContainer = findViewById(R.id.llStudentTimelineContainer)
        rvTimeline = findViewById(R.id.rvStudentTimeline)
        tvTimelineEmpty = findViewById(R.id.tvStudentTimelineEmpty)
        rvTimeline.layoutManager = LinearLayoutManager(this)
        rvTimeline.isNestedScrollingEnabled = false
        timelineAdapter = TimelineAdapter(emptyList())
        rvTimeline.adapter = timelineAdapter

        tvTotalDebt = findViewById(R.id.tvTotalDebt)
        tvDebtTeacher = findViewById(R.id.tvDebtTeacher)
        tvDebtInstitute = findViewById(R.id.tvDebtInstitute)
        btnInvoice = findViewById(R.id.btnIssueInvoice)

        // A1: bind installments views
        cardContent = findViewById(R.id.cardContent)
        cardInstallments = findViewById(R.id.cardInstallments)
        rvInstallments = findViewById(R.id.rvInstallments)
        tvInstallmentsEmpty = findViewById(R.id.tvInstallmentsEmpty)
        btnAddInstallment = findViewById(R.id.btnAddInstallment)
        rvInstallments.layoutManager = LinearLayoutManager(this)
        rvInstallments.isNestedScrollingEnabled = false
        installmentAdapter = InstallmentAdapter(emptyList(),
            onPay = { item -> confirmAndPayInstallment(item) },
            onRemind = { item -> confirmAndRemindInstallment(item) }
        )
        rvInstallments.adapter = installmentAdapter
        // FIX (گروه۳/آیتم۱۴): چک نقش — همان الگوی موجودِ پروژه (`UserCreds` → `USER_SUB_ROLE`).
        // معلم از دلِ کلاس (حضور و غیاب / راه‌اندازی کلاس / کلاس زنده) به این صفحه می‌رسد و
        // نباید هیچ اکشن پولی یا مدیریتی ببیند: «صدور فیش و ثبت حواله»، کلید «تعلیق
        // دانش‌آموز»، «حذف کامل دانش‌آموز»، «افزودن قسط جدید»، «پرداخت/یادآوری قسط»،
        // «ارسال لینک پورتال به اولیا» و ویرایش پروفایل (شامل تغییر عکس).
        // نمای خواندنی (تب‌ها، آمار بدهی، کارنامه، اقساط، ارتباطات، تایم‌لاین) دست‌نخورده است.
        // گارد عمداً روی `"teacher"` است نه `!= "admin"`: «منشی» در این اپ نقش وصول پول دارد
        // (endpointهای مالی سرور `("admin","secretary")`) و رفتار قبلی‌اش حفظ می‌شود.
        val credsPrefs = getSharedPreferences("UserCreds", Context.MODE_PRIVATE)
        val subRole = credsPrefs.getString("USER_SUB_ROLE", "admin") ?: "admin"
        isTeacherUser = subRole == "teacher"
        if (isTeacherUser) {
            btnInvoice.visibility = View.GONE
            btnAddInstallment.visibility = View.GONE
            findViewById<View>(R.id.cardSuspendStudent).visibility = View.GONE
            findViewById<View>(R.id.btnDeleteStudent).visibility = View.GONE
            findViewById<View>(R.id.btnSendPortalLink).visibility = View.GONE
            findViewById<View>(R.id.fabEditProfile).visibility = View.GONE
        }
        if (subRole == "secretary") {
            findViewById<View>(R.id.btnDeleteStudent).visibility = View.GONE
        }

        // listenerها هم فقط برای غیر معلم ثبت می‌شوند (ویجت پنهانِ کلیک‌پذیر = راه فرار).
        if (!isTeacherUser) {
            btnAddInstallment.setOnClickListener { showCreateInstallmentDialog() }

            findViewById<MaterialButton>(R.id.btnDeleteStudent).setOnClickListener {
                showDeleteConfirmation()
            }

            findViewById<MaterialButton>(R.id.btnSendPortalLink).setOnClickListener {
                sendPortalLinkToParent()
            }

            findViewById<android.widget.ImageView>(R.id.imgProfile).setOnClickListener {
                showImageSelectDialog()
            }

            switchSuspend.setOnClickListener {
                toggleStudentSuspension()
            }

            btnInvoice.setOnClickListener {
                launchInvoiceActivity()
            }
        }
    }

    private fun fetchFullData() {
        val retrofit = RetrofitClient.getInstance(this)
        val api = retrofit.create(ProfileApi::class.java)

        val cacheKey = "student_full_profile_" + studentId
        val type = object : com.google.gson.reflect.TypeToken<FullStudentProfile>() {}.type

        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.

        lifecycleScope.launch(Dispatchers.Main) {
            CachedApiCall.execute(
                context = this@StudentProfileActivity,
                cacheKey = cacheKey,
                type = type,
                networkCall = { api.getFullStudentProfile(studentId) },
                onSuccess = { data, isOffline, timestamp ->
                    cachedProfile = data
                    tvName.text = data.info.name
                    tvPhone.text = data.info.student_mobile

                    // بارگذاری عکس پروفایل با Glide
                    val profileImg = findViewById<android.widget.ImageView>(R.id.imgProfile)
                    if (!data.info.profile_image.isNullOrEmpty()) {
                        val baseUrl = RetrofitClient.getInstance(this@StudentProfileActivity).baseUrl().toString()
                        val imgUrl = baseUrl + "uploads/profiles/" + data.info.profile_image
                        val glideAuthToken = SecureLoginStore.getToken(this@StudentProfileActivity)  // FIX M22.
                        // FIX M3: Glide با هدر احراز (اندپوینت /uploads دیگر عمومی نیست).
                        val glideUrl = com.bumptech.glide.load.model.GlideUrl(
                            imgUrl,
                            com.bumptech.glide.load.model.LazyHeaders.Builder()
                                .addHeader("Authorization", "Bearer $glideAuthToken")
                                .build()
                        )
                        com.bumptech.glide.Glide.with(this@StudentProfileActivity)
                            .load(glideUrl)
                            .placeholder(android.R.drawable.sym_def_app_icon)
                            .error(android.R.drawable.sym_def_app_icon)
                            .circleCrop()
                            .into(profileImg)
                    } else {
                        profileImg.setImageDrawable(AvatarHelper.getAvatar(this@StudentProfileActivity, data.info.name, studentId))
                    }

                    switchSuspend.setOnCheckedChangeListener(null)
                    switchSuspend.isChecked = data.info.is_suspended
                    switchSuspend.setOnClickListener { toggleStudentSuspension() }

                    // ===========================================
                    // 🔥 لاجیک جدید نمایش مالی (هوشمند)
                    // ===========================================

                    // بدهی کلی/کیف کلی به‌عنوان بدهی کلاس نمایش داده نمی‌شود؛
                    // اعداد دقیق فقط در تب مالی و بر اساس enrollment دیده می‌شوند.
                    tvTotalDebt.text = "بدهی هر کلاس در تب مالی به‌صورت تفکیک‌شده نمایش داده می‌شود"
                    tvTotalDebt.setTextColor(UiColors.resolve(this@StudentProfileActivity, R.color.text_primary))
                    tvDebtTeacher.visibility = View.GONE
                    tvDebtInstitute.visibility = View.GONE
                    // ===========================================

                    if (tabLayout.selectedTabPosition == 0) showInfo()
                    else if (tabLayout.selectedTabPosition == 1) showFinancial()
                    else if (tabLayout.selectedTabPosition == 3) fetchInstallments()

                    if (isOffline) {
                        CachedApiCall.showOfflineBanner(this@StudentProfileActivity, timestamp)
                    } else {
                        CachedApiCall.hideOfflineBanner(this@StudentProfileActivity)
                    }
                },
                onFailure = {
                    tvContent.text = getString(R.string.common_offline_empty)
                }
            )
        }
    }

    private fun launchInvoiceActivity() {
        val profile = cachedProfile ?: return
        val fallbackName = profile.classes.firstOrNull() ?: getString(R.string.common_unknown_class)
        val enrollments = profile.enrollments
        when {
            enrollments.size == 1 -> {
                // FIX(invoice): تنها کلاس فعال → شناسه‌ی واقعی همان enrollment می‌رود (نه نام نمایشی)
                val en = enrollments[0]
                openInvoice(en.enrollment_id, en.course_id, EnrollmentLabels.classTitle(this, en), en)
            }
            enrollments.size > 1 -> {
                // FIX(invoice): چند کلاس فعال → اول انتخاب کلاس (با شناسه واقعی)؛ فیش هرگز با نام کلاس حدس‌زده نمی‌شود
                // هر ردیف: کلاس (کد) / معلم / بدهی به معلم (نام معلم) / بدهی به آموزشگاه / برای چند جلسه
                val labels = enrollments.map { EnrollmentLabels.pickerLabel(this, it) }
                AlertDialog.Builder(this)
                    .setTitle(getString(R.string.invoice_pick_class, profile.info.name))
                    .setItems(labels.toTypedArray()) { _, which ->
                        val en = enrollments[which]
                        openInvoice(en.enrollment_id, en.course_id, EnrollmentLabels.classTitle(this, en), en)
                    }
                    .setNegativeButton(R.string.common_cancel, null)
                    .show()
            }
            else -> {
                // enrollment فعالی نیست (سرور قدیمی یا واقعاً بدون کلاس) → رفتار قبلی: فیش عمومی
                openInvoice(null, -1, fallbackName, null)
            }
        }
    }

    private fun openInvoice(enrollmentId: Int?, courseId: Int, className: String, selected: ActiveStudentEnrollment? = null) {
        val profile = cachedProfile ?: return
        val intent = Intent(this, InvoiceActivity::class.java).apply {
            putExtra(InvoiceActivity.EXTRA_PREFILL_STUDENT_ID, studentId)
            putExtra(InvoiceActivity.EXTRA_PREFILL_STUDENT_NAME, profile.info.name)
            putExtra(InvoiceActivity.EXTRA_PREFILL_CLASS_NAME, className)
            // Prefill is scoped to the selected enrollment; the profile totals remain
            // the fallback only for legacy responses that omit enrollment debt fields.
            putExtra(InvoiceActivity.EXTRA_PREFILL_DEBT, selected?.total_debt ?: profile.totalDebt)
            putExtra(InvoiceActivity.EXTRA_PREFILL_DEBT_TEACHER, selected?.debt_teacher ?: profile.debtTeacher)
            putExtra(InvoiceActivity.EXTRA_PREFILL_DEBT_INSTITUTE, selected?.debt_institute ?: profile.debtInstitute)
            putExtra(InvoiceActivity.EXTRA_PREFILL_UNPAID_SESSIONS, 0)
            putExtra(InvoiceActivity.EXTRA_PREFILL_SEARCH_NAME, profile.info.name)
            putExtra(InvoiceActivity.EXTRA_IS_ADMIN, true)
            // FIX(invoice): شناسه‌های واقعی (فقط وقتی enrollment معتبر انتخاب/مشخص است)
            if (enrollmentId != null && enrollmentId > 0) {
                putExtra(InvoiceActivity.EXTRA_PREFILL_ENROLLMENT_ID, enrollmentId)
                putExtra(InvoiceActivity.EXTRA_PREFILL_COURSE_ID, courseId)
            }
        }
        startActivity(intent)
    }

    private fun showInfo() {
        cachedProfile?.let { data ->
            val sb = StringBuilder()
            if (data.info.is_suspended) sb.append(getString(R.string.profile_suspended))
            if (data.info.student_code != null) sb.append(getString(R.string.profile_code, data.info.student_code))
            sb.append(getString(R.string.profile_name, data.info.name))
            sb.append(getString(R.string.profile_national, data.info.national_code))
            sb.append(getString(R.string.profile_mobile, data.info.student_mobile))
            sb.append(getString(R.string.profile_parent, data.info.parent_mobile))
            sb.append(getString(R.string.profile_address, data.info.address))

            tvContent.setOnClickListener { makeCall(data.info.parent_mobile) }
            tvContent.text = sb.toString()
        }
    }

    private fun showFinancial() {
        cachedProfile?.let { data ->
            val sb = StringBuilder()
            sb.append(getString(R.string.profile_classes_title))
            if (data.classes.isEmpty()) sb.append(getString(R.string.profile_no_class))
            else data.classes.forEach { sb.append(getString(R.string.profile_bullet_row, it)) }

            sb.append(getString(R.string.profile_txn_title))
            if (data.transactions.isEmpty()) sb.append(getString(R.string.profile_no_txn))
            else data.transactions.forEach { sb.append(getString(R.string.profile_bullet_row, it)) }

            // بدهی فقط در سطح enrollment نمایش داده می‌شود؛ کیف کلی دانش‌آموز
            // به هیچ‌کدام از کلاس‌ها نسبت داده نمی‌شود.
            data.teachers_financial?.let { rows ->
                if (rows.isNotEmpty()) {
                    sb.append("\nبدهی تفکیک‌شده کلاس‌ها:\n")
                    rows.forEach { row ->
                        if (row.is_unassigned) {
                            sb.append("بدهی بدون کلاس — آموزشگاه: ${formatCurrency(row.debt_institute)}\n")
                        } else {
                            val classLabel = EnrollmentLabels.classTitle(this, row.course_title, row.course_code)
                            sb.append("کلاس $classLabel — معلم ${row.teacher_name ?: "بدون معلم"}\n")
                            // نام معلم جلوی بدهی به معلم؛ هر کلاس جدا (دو کلاسِ هم‌معلم جمع نمی‌شوند)
                            sb.append("  ${EnrollmentLabels.debtTeacherLine(this, row.teacher_name, row.debt_teacher)}\n")
                            sb.append("  ${EnrollmentLabels.debtInstituteLine(this, row.debt_institute)}\n")
                            // «این بدهی برای چند جلسه است؟»
                            if (row.contract_only) sb.append(getString(R.string.profile_class_contract_line))
                            else if (row.sessions_billed != null && (row.unpaid_sessions ?: 0) > 0)
                                sb.append(getString(R.string.profile_class_sessions_line, row.unpaid_sessions.toString(), row.sessions_billed.toString()))
                        }
                    }
                }
            }

            tvContent.text = sb.toString()
            tvContent.setOnClickListener(null)
        }
    }

    private fun fetchGrades() {
        tvContent.text = getString(R.string.profile_grades_loading)
        val retrofit = RetrofitClient.getInstance(this)
        val api = retrofit.create(ProfileApi::class.java)

        val cacheKey = "student_grades_" + studentId
        val type = object : com.google.gson.reflect.TypeToken<StudentGradesResponse>() {}.type

        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.

        lifecycleScope.launch(Dispatchers.Main) {
            CachedApiCall.execute(
                context = this@StudentProfileActivity,
                cacheKey = cacheKey,
                type = type,
                networkCall = { api.getStudentGrades(studentId) },
                onSuccess = { res, isOffline, timestamp ->
                    val sb = StringBuilder()
                    sb.append(getString(R.string.profile_report_title))
                    if (res.grades.isEmpty()) {
                        sb.append(getString(R.string.profile_no_grades))
                    } else {
                        if (res.averages.isNotEmpty()) {
                            sb.append(getString(R.string.profile_avg_title))
                            res.averages.forEach { (course, avg) ->
                                sb.append(getString(R.string.profile_avg_row, course, avg))
                            }
                            sb.append("============================\n\n")
                        }

                        sb.append(getString(R.string.profile_grades_list))
                        res.grades.forEach { g ->
                            sb.append(getString(R.string.profile_grade_course, g.courseName))
                            sb.append(getString(R.string.profile_grade_exam, g.examTitle))
                            sb.append(getString(R.string.profile_grade_score, g.score, g.maxScore))
                            sb.append(getString(R.string.profile_grade_date, g.date))
                            if (!g.description.isNullOrEmpty()) sb.append(getString(R.string.profile_grade_desc, g.description))
                            sb.append("----------------------------\n")
                        }
                    }
                    tvContent.text = sb.toString()
                    if (isOffline) {
                        CachedApiCall.showOfflineBanner(this@StudentProfileActivity, timestamp)
                    } else {
                        CachedApiCall.hideOfflineBanner(this@StudentProfileActivity)
                    }
                },
                onFailure = {
                    tvContent.text = getString(R.string.common_offline_empty)
                }
            )
        }
    }

    private fun showStandardProfileContent() {
        llStandardContainer.visibility = View.VISIBLE
        llCommunicationContainer.visibility = View.GONE
        if (::llTimelineContainer.isInitialized) llTimelineContainer.visibility = View.GONE
        if (::cardContent.isInitialized) cardContent.visibility = View.VISIBLE
        if (::cardInstallments.isInitialized) cardInstallments.visibility = View.GONE
    }

    private fun showInstallmentsContent() {
        llStandardContainer.visibility = View.VISIBLE
        llCommunicationContainer.visibility = View.GONE
        if (::llTimelineContainer.isInitialized) llTimelineContainer.visibility = View.GONE
        if (::cardContent.isInitialized) cardContent.visibility = View.GONE
        if (::cardInstallments.isInitialized) cardInstallments.visibility = View.VISIBLE
        // مالی کارت را هم نگه می‌داریم (مثل قبل) — فقط محتوای متنی جایگزین می‌شود
        if (::tvInstallmentsEmpty.isInitialized) {
            tvInstallmentsEmpty.visibility = View.VISIBLE
            tvInstallmentsEmpty.text = getString(R.string.profile_inst_loading)
        }
        if (::rvInstallments.isInitialized) rvInstallments.visibility = View.GONE
    }

    private fun showCommunicationContent() {
        llStandardContainer.visibility = View.GONE
        llCommunicationContainer.visibility = View.VISIBLE
        if (::llTimelineContainer.isInitialized) llTimelineContainer.visibility = View.GONE
        if (::cardInstallments.isInitialized) cardInstallments.visibility = View.GONE
    }

    private fun showTimelineContent() {
        llStandardContainer.visibility = View.GONE
        llCommunicationContainer.visibility = View.GONE
        if (::cardInstallments.isInitialized) cardInstallments.visibility = View.GONE
        if (::llTimelineContainer.isInitialized) llTimelineContainer.visibility = View.VISIBLE
        if (::tvTimelineEmpty.isInitialized) {
            tvTimelineEmpty.visibility = View.VISIBLE
            tvTimelineEmpty.text = getString(R.string.timeline_loading)
        }
        if (::rvTimeline.isInitialized) rvTimeline.visibility = View.GONE
    }

    private fun fetchCommunicationHistory() {
        tvCommunicationEmpty.visibility = View.VISIBLE
        tvCommunicationEmpty.text = getString(R.string.profile_comm_loading)
        rvCommunicationHistory.visibility = View.GONE

        val api = RetrofitClient.getInstance(this).create(ProfileApi::class.java)
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val history = api.getStudentCommunicationHistory(studentId)
                withContext(Dispatchers.Main) {
                    rvCommunicationHistory.adapter = CommunicationHistoryAdapter(history)
                    rvCommunicationHistory.visibility =
                        if (history.isEmpty()) View.GONE else View.VISIBLE
                    tvCommunicationEmpty.visibility =
                        if (history.isEmpty()) View.VISIBLE else View.GONE
                    if (history.isEmpty()) {
                        tvCommunicationEmpty.text = getString(R.string.profile_comm_empty)
                    }
                }
            } catch (ignoredError: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (ignoredError is kotlinx.coroutines.CancellationException) throw ignoredError;
                withContext(Dispatchers.Main) {
                    rvCommunicationHistory.visibility = View.GONE
                    tvCommunicationEmpty.visibility = View.VISIBLE
                    tvCommunicationEmpty.text =
                        getString(R.string.profile_comm_error)
                }
            }
        }
    }

    private fun fetchTimeline() {
        tvTimelineEmpty.visibility = View.VISIBLE
        tvTimelineEmpty.text = getString(R.string.timeline_loading)
        rvTimeline.visibility = View.GONE

        val api = RetrofitClient.getInstance(this).create(TimelineApi::class.java)
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val list = api.getTimeline(studentId)
                withContext(Dispatchers.Main) {
                    if (list.isEmpty()) {
                        tvTimelineEmpty.visibility = View.VISIBLE
                        tvTimelineEmpty.text = getString(R.string.timeline_empty)
                        rvTimeline.visibility = View.GONE
                    } else {
                        tvTimelineEmpty.visibility = View.GONE
                        rvTimeline.visibility = View.VISIBLE
                        timelineAdapter?.update(list)
                    }
                }
            } catch (e: Exception) {
                if (e is kotlinx.coroutines.CancellationException) throw e
                withContext(Dispatchers.Main) {
                    rvTimeline.visibility = View.GONE
                    tvTimelineEmpty.visibility = View.VISIBLE
                    val detail = try {
                        if (e is retrofit2.HttpException) {
                            val body = e.response()?.errorBody()?.string()
                            if (!body.isNullOrBlank()) {
                                val obj = org.json.JSONObject(body)
                                obj.optString("detail", e.message ?: getString(R.string.common_unknown_error))
                            } else e.message ?: getString(R.string.common_unknown_error)
                        } else e.message ?: getString(R.string.common_unknown_error)
                    } catch (_: Exception) { e.message ?: getString(R.string.common_unknown_error) }
                    tvTimelineEmpty.text = getString(R.string.timeline_error, detail)
                }
            }
        }
    }

    private fun makeCall(number: String) {
        if (number.length < 3) return
        try { startActivity(Intent(Intent.ACTION_DIAL, Uri.parse("tel:$number"))) } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;}
    }

    private fun showDeleteConfirmation() {
        AlertDialog.Builder(this)
            .setTitle(getString(R.string.profile_delete_title))
            .setMessage(getString(R.string.profile_delete_msg))
            .setPositiveButton(getString(R.string.profile_delete_yes)) { _, _ -> performDelete() }
            .setNegativeButton(getString(R.string.action_cancel), null)
            .show()
    }

    private fun performDelete() {
        val retrofit = RetrofitClient.getInstance(this)
        val api = retrofit.create(ProfileApi::class.java)
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val res = api.deleteStudent(studentId)
                withContext(Dispatchers.Main) {
                    // بازخورد لمسی برای عملیات حذف برگشت‌ناپذیر موفق
                    window.decorView.performHapticFeedback(android.view.HapticFeedbackConstants.VIRTUAL_KEY)

                    Toast.makeText(this@StudentProfileActivity, res.message, Toast.LENGTH_LONG).show()
                    
                    // ابطال کش
                    CacheManager.clear(this@StudentProfileActivity, "student_full_profile_$studentId")
                    CacheManager.clearByPrefix(this@StudentProfileActivity, "person_list_STUDENT")
                    
                    finish()
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) { Toast.makeText(this@StudentProfileActivity, getString(R.string.profile_delete_error), Toast.LENGTH_SHORT).show() }
            }
        }
    }

    private fun toggleStudentSuspension() {
        switchSuspend.isEnabled = false
        val retrofit = RetrofitClient.getInstance(this)
        val api = retrofit.create(ProfileApi::class.java)
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val res = api.toggleSuspend(studentId)
                withContext(Dispatchers.Main) {
                    com.google.android.material.snackbar.Snackbar.make(
                        findViewById(android.R.id.content),
                        getString(R.string.common_ok_msg, res.message),
                        com.google.android.material.snackbar.Snackbar.LENGTH_LONG
                    ).show()
                    switchSuspend.isChecked = res.is_suspended
                    switchSuspend.isEnabled = true
                    
                    // ابطال کش
                    CacheManager.clear(this@StudentProfileActivity, "student_full_profile_$studentId")
                    CacheManager.clearByPrefix(this@StudentProfileActivity, "person_list_STUDENT")
                    
                    if (tabLayout.selectedTabPosition == 0) {
                        cachedProfile?.let {
                            cachedProfile = it.copy(info = it.info.copy(is_suspended = res.is_suspended))
                            showInfo()
                        }
                    }
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@StudentProfileActivity, getString(R.string.profile_status_error), Toast.LENGTH_SHORT).show()
                    switchSuspend.isChecked = !switchSuspend.isChecked
                    switchSuspend.isEnabled = true
                }
            }
        }
    }

    private fun buildTotalStatus(walletBalance: Long, totalDebt: Long): String {
        val balanceSection = when {
            walletBalance < 0 -> getString(R.string.profile_debt_total, formatCurrency(abs(walletBalance)))
            walletBalance > 0 -> getString(R.string.profile_credit_total, formatCurrency(walletBalance))
            else -> getString(R.string.profile_settled_total)
        }

        val debtSection = if (totalDebt > 0) getString(R.string.profile_debt_reg, formatCurrency(totalDebt)) else ""
        return balanceSection + debtSection
    }

    private fun buildWalletStatus(label: String, balance: Long, debt: Long): String {
        val status = when {
            balance < 0 -> getString(R.string.profile_ower, formatCurrency(abs(balance)))
            balance > 0 -> getString(R.string.profile_creditor, formatCurrency(balance))
            else -> getString(R.string.profile_settled)
        }

        val debtSection = if (debt > 0) getString(R.string.profile_debt_short, formatCurrency(debt)) else ""
        return "$label: $status$debtSection"
    }

    private fun colorForBalance(balance: Long): Int = when {
        balance < 0 -> UiColors.resolve(this, R.color.status_danger)
        balance > 0 -> UiColors.resolve(this, R.color.status_success)
        else -> UiColors.resolve(this, R.color.text_secondary)
    }

    private fun formatCurrency(value: Long): String =
        String.format(Locale("en", "US"), "%,d", abs(value))

    // --- منطق جدید عکس پروفایل (آپلود فیزیکی، گالری، دوربین و دسترسی‌ها) ---
    private fun showImageSelectDialog() {
        val options = arrayOf(getString(R.string.profile_photo_camera), getString(R.string.profile_photo_gallery))
        AlertDialog.Builder(this)
            .setTitle(getString(R.string.profile_photo_title))
            .setItems(options) { _, which ->
                if (which == 0) {
                    if (checkSelfPermission(android.Manifest.permission.CAMERA) != android.content.pm.PackageManager.PERMISSION_GRANTED) {
                        requestPermissions(arrayOf(android.Manifest.permission.CAMERA), 101)
                    } else {
                        openCamera()
                    }
                } else {
                    openGallery()
                }
            }
            .show()
    }

    private fun openGallery() {
        val intent = Intent(Intent.ACTION_PICK)
        intent.type = "image/*"
        startActivityForResult(intent, 201)
    }

    private fun openCamera() {
        val intent = Intent(android.provider.MediaStore.ACTION_IMAGE_CAPTURE)
        startActivityForResult(intent, 202)
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == 101 && grantResults.isNotEmpty() && grantResults[0] == android.content.pm.PackageManager.PERMISSION_GRANTED) {
            openCamera()
        } else {
            Toast.makeText(this, getString(R.string.profile_camera_denied), Toast.LENGTH_SHORT).show()
        }
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (resultCode == RESULT_OK) {
            if (requestCode == 201) { // Gallery
                val uri = data?.data
                if (uri != null) {
                    uploadImageUri(uri)
                }
            } else if (requestCode == 202) { // Camera
                val bitmap = data?.extras?.get("data") as? android.graphics.Bitmap
                if (bitmap != null) {
                    uploadImageBitmap(bitmap)
                }
            }
        }
    }

    private fun uploadImageUri(uri: Uri) {
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val inputStream = contentResolver.openInputStream(uri)
                val file = java.io.File(cacheDir, "temp_profile.jpg")
                val outputStream = java.io.FileOutputStream(file)
                inputStream?.copyTo(outputStream)
                outputStream.flush()
                outputStream.close()
                inputStream?.close()
                
                uploadFileToServer(file)
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@StudentProfileActivity, getString(R.string.profile_image_error), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun uploadImageBitmap(bitmap: android.graphics.Bitmap) {
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val file = java.io.File(cacheDir, "temp_profile.jpg")
                val outputStream = java.io.FileOutputStream(file)
                bitmap.compress(android.graphics.Bitmap.CompressFormat.JPEG, 90, outputStream)
                outputStream.flush()
                outputStream.close()
                
                uploadFileToServer(file)
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@StudentProfileActivity, getString(R.string.profile_image_error), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun uploadFileToServer(file: java.io.File) {
        val requestFile = okhttp3.RequestBody.create(okhttp3.MediaType.parse("image/*"), file)
        val body = okhttp3.MultipartBody.Part.createFormData("file", file.name, requestFile)
        
        val retrofit = RetrofitClient.getInstance(this)
        val api = retrofit.create(ProfileApi::class.java)
        
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val response = api.uploadStudentPhoto(studentId, body)
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@StudentProfileActivity, getString(R.string.common_ok_msg, response.message), Toast.LENGTH_SHORT).show()
                    fetchFullData() // رفرش خودکار عکس پروفایل
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@StudentProfileActivity, getString(R.string.profile_upload_error), Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    // A1: واکشی لیست اقساط با RecyclerView + دکمه‌های پرداخت/یادآوری/افزودن
    private fun fetchInstallments() {
        // نمایش حالت لودینگ در کانتینر اقساط
        if (::cardInstallments.isInitialized) {
            cardInstallments.visibility = View.VISIBLE
            cardContent.visibility = View.GONE
            tvInstallmentsEmpty.visibility = View.VISIBLE
            tvInstallmentsEmpty.text = getString(R.string.profile_inst_loading)
            rvInstallments.visibility = View.GONE
        } else {
            tvContent.text = getString(R.string.profile_inst_loading)
        }
        val retrofit = RetrofitClient.getInstance(this)
        val api = retrofit.create(ProfileApi::class.java)

        val cacheKey = "student_installments_" + studentId
        val type = object : com.google.gson.reflect.TypeToken<List<StudentInstallmentItem>>() {}.type

        lifecycleScope.launch(Dispatchers.Main) {
            CachedApiCall.execute(
                context = this@StudentProfileActivity,
                cacheKey = cacheKey,
                type = type,
                networkCall = { api.getStudentInstallments(studentId) },
                onSuccess = { list, isOffline, timestamp ->
                    currentInstallments = list
                    if (list.isEmpty()) {
                        tvInstallmentsEmpty.visibility = View.VISIBLE
                        tvInstallmentsEmpty.text = getString(R.string.installment_no_installments)
                        rvInstallments.visibility = View.GONE
                    } else {
                        tvInstallmentsEmpty.visibility = View.GONE
                        rvInstallments.visibility = View.VISIBLE
                        installmentAdapter?.update(list)
                    }
                    if (isOffline) {
                        CachedApiCall.showOfflineBanner(this@StudentProfileActivity, timestamp)
                    } else {
                        CachedApiCall.hideOfflineBanner(this@StudentProfileActivity)
                    }
                },
                onFailure = {
                    tvInstallmentsEmpty.visibility = View.VISIBLE
                    tvInstallmentsEmpty.text = getString(R.string.common_offline_empty)
                    rvInstallments.visibility = View.GONE
                }
            )
        }
    }

    // ———————————————— A1: helpers ————————————————
    private fun extractServerDetail(e: Exception): String? {
        return try {
            if (e is retrofit2.HttpException) {
                val body = e.response()?.errorBody()?.string()
                if (!body.isNullOrBlank()) {
                    val obj = org.json.JSONObject(body)
                    val d = obj.optString("detail", "")
                    if (d.isNotBlank()) d else obj.optString("message", null)?.takeIf { it.isNotBlank() }
                } else null
            } else null
        } catch (_: Exception) { null }
    }

    private fun normalizePersianDigits(input: String): String {
        val fa = "۰۱۲۳۴۵۶۷۸۹"
        val ar = "٠١٢٣٤٥٦٧٨٩"
        val sb = StringBuilder(input.length)
        for (c in input) {
            val fi = fa.indexOf(c)
            val ai = if (fi >= 0) -1 else ar.indexOf(c)
            sb.append(when {
                fi >= 0 -> ('0' + fi)
                ai >= 0 -> ('0' + ai)
                else -> c
            })
        }
        return sb.toString()
    }

    private fun isValidJalaliDate(raw: String): Boolean {
        val normalized = normalizePersianDigits(raw.trim())
        val re = Regex("^\\\\d{4}/\\\\d{2}/\\\\d{2}$")
        if (!re.matches(normalized)) return false
        return try {
            JalaliUtils.parseProjectDate(normalized) != null
        } catch (_: Exception) { false }
    }

    // ———————————————— A1: پرداخت ————————————————
    private fun confirmAndPayInstallment(item: StudentInstallmentItem) {
        AlertDialog.Builder(this)
            .setTitle(getString(R.string.installment_pay_title))
            .setMessage(getString(R.string.installment_pay_msg, String.format(java.util.Locale("en","US"), "%,d", item.amount)))
            .setPositiveButton(getString(R.string.installment_pay_yes)) { _, _ -> performPayInstallment(item.id) }
            .setNegativeButton(getString(R.string.common_cancel), null)
            .show()
    }

    private fun performPayInstallment(installmentId: Int) {
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@StudentProfileActivity, getString(R.string.installment_paying), Toast.LENGTH_SHORT).show()
                }
                val api = RetrofitClient.getInstance(this@StudentProfileActivity).create(InstallmentApi::class.java)
                val res = api.payInstallment(installmentId)
                withContext(Dispatchers.Main) {
                    val msg = res.message.takeIf { it.isNotBlank() } ?: getString(R.string.installment_pay_success)
                    Toast.makeText(this@StudentProfileActivity, msg, Toast.LENGTH_LONG).show()
                    CacheManager.clear(this@StudentProfileActivity, "student_installments_" + studentId)
                    fetchInstallments()
                    fetchFullData()
                }
            } catch (e: Exception) {
                if (e is kotlinx.coroutines.CancellationException) throw e
                withContext(Dispatchers.Main) {
                    val detail = extractServerDetail(e) ?: e.message ?: getString(R.string.common_unknown_error)
                    Toast.makeText(this@StudentProfileActivity, getString(R.string.common_err_with_detail, detail), Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    // ———————————————— A1: یادآوری ————————————————
    private fun confirmAndRemindInstallment(item: StudentInstallmentItem) {
        AlertDialog.Builder(this)
            .setTitle(getString(R.string.installment_remind_title))
            .setMessage(getString(R.string.installment_remind_msg))
            .setPositiveButton(getString(R.string.installment_remind)) { _, _ -> performRemindInstallment(item.id) }
            .setNegativeButton(getString(R.string.common_cancel), null)
            .show()
    }

    private fun performRemindInstallment(installmentId: Int) {
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@StudentProfileActivity, getString(R.string.installment_remind_sending), Toast.LENGTH_SHORT).show()
                }
                val api = RetrofitClient.getInstance(this@StudentProfileActivity).create(InstallmentApi::class.java)
                val res = api.remindInstallment(installmentId)
                withContext(Dispatchers.Main) {
                    val msg = res.message.takeIf { it.isNotBlank() } ?: getString(R.string.installment_remind_success)
                    Toast.makeText(this@StudentProfileActivity, msg, Toast.LENGTH_LONG).show()
                }
            } catch (e: Exception) {
                if (e is kotlinx.coroutines.CancellationException) throw e
                withContext(Dispatchers.Main) {
                    // حتی 400 (موبایل ولی ثبت نشده) باید پیام سرور نمایش داده شود — الزام تسک
                    val detail = extractServerDetail(e) ?: e.message ?: getString(R.string.common_unknown_error)
                    Toast.makeText(this@StudentProfileActivity, getString(R.string.common_err_with_detail, detail), Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    // ———————————————— A1: افزودن قسط جدید ————————————————
    private fun showCreateInstallmentDialog() {
        // ابتدا enrollment های فعال را از dashboard بگیریم
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@StudentProfileActivity, getString(R.string.installment_loading_enrollments), Toast.LENGTH_SHORT).show()
                }
                val dashApi = RetrofitClient.getInstance(this@StudentProfileActivity).create(FinanceDashboardApi::class.java)
                val dash = dashApi.getFinancialDashboard(studentId)
                val enrollments = dash.enrollments
                withContext(Dispatchers.Main) {
                    if (enrollments.isEmpty()) {
                        Toast.makeText(this@StudentProfileActivity, getString(R.string.installment_error_no_enrollment), Toast.LENGTH_LONG).show()
                        return@withContext
                    }
                    val courseNames = enrollments.map { it.courseTitle }
                    val courseIds = enrollments.map { it.enrollmentId }

                    val dialogView = LayoutInflater.from(this@StudentProfileActivity).inflate(R.layout.dialog_create_installment, null)
                    val tilCourse = dialogView.findViewById<TextInputLayout>(R.id.tilInstallmentCourse)
                    val actvCourse = dialogView.findViewById<AutoCompleteTextView>(R.id.actvInstallmentCourse)
                    val etAmount = dialogView.findViewById<TextInputEditText>(R.id.etInstallmentAmount)
                    val etDue = dialogView.findViewById<TextInputEditText>(R.id.etInstallmentDue)
                    val tilDue = dialogView.findViewById<TextInputLayout>(R.id.tilInstallmentDue)

                    val adapter = ArrayAdapter(this@StudentProfileActivity, android.R.layout.simple_dropdown_item_1line, courseNames)
                    actvCourse.setAdapter(adapter)
                    if (enrollments.size == 1) {
                        actvCourse.setText(courseNames[0], false)
                        actvCourse.isEnabled = false
                        tilCourse.isEnabled = false
                    } else {
                        actvCourse.setText(courseNames[0], false)
                    }
                    // پیش‌فرض سررسید: امروز شمسی
                    etDue.setText(JalaliUtils.todayJalaliString())
                    tilDue.setEndIconOnClickListener {
                        // فوکوس ساده — تقویم شمسی در این فرم با تایپ مستقیم پر می‌شود (هم‌سبک بقیه اپ)
                        etDue.requestFocus()
                    }

                    val dialog = AlertDialog.Builder(this@StudentProfileActivity)
                        .setTitle(getString(R.string.installment_create_title))
                        .setView(dialogView)
                        .setPositiveButton(getString(R.string.action_save), null)
                        .setNegativeButton(getString(R.string.common_cancel), null)
                        .create()
                    dialog.show()
                    dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener {
                        val selected = actvCourse.text?.toString()?.trim() ?: ""
                        val idx = courseNames.indexOf(selected)
                        if (idx == -1) {
                            Toast.makeText(this@StudentProfileActivity, getString(R.string.installment_error_no_enrollment), Toast.LENGTH_SHORT).show()
                            return@setOnClickListener
                        }
                        val enrollmentId = courseIds[idx]
                        val rawAmount = etAmount.text?.toString()?.trim() ?: ""
                        val normalizedAmountStr = normalizePersianDigits(rawAmount).replace(",", "").replace("٬", "").replace(" ", "")
                        val amount = normalizedAmountStr.toIntOrNull()
                        if (amount == null || amount <= 0) {
                            etAmount.error = getString(R.string.installment_error_amount)
                            Toast.makeText(this@StudentProfileActivity, getString(R.string.installment_error_amount), Toast.LENGTH_SHORT).show()
                            return@setOnClickListener
                        }
                        if (amount > 1_000_000_000) {
                            etAmount.error = getString(R.string.installment_error_amount)
                            return@setOnClickListener
                        }
                        val rawDue = etDue.text?.toString()?.trim() ?: ""
                        val normalizedDue = normalizePersianDigits(rawDue)
                        if (!isValidJalaliDate(normalizedDue)) {
                            etDue.error = getString(R.string.installment_error_due)
                            Toast.makeText(this@StudentProfileActivity, getString(R.string.installment_error_due), Toast.LENGTH_SHORT).show()
                            return@setOnClickListener
                        }
                        dialog.dismiss()
                        performCreateInstallment(enrollmentId, amount, normalizedDue)
                    }
                }
            } catch (e: Exception) {
                if (e is kotlinx.coroutines.CancellationException) throw e
                withContext(Dispatchers.Main) {
                    val detail = extractServerDetail(e) ?: e.message ?: getString(R.string.common_unknown_error)
                    Toast.makeText(this@StudentProfileActivity, getString(R.string.common_err_with_detail, detail), Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    private fun performCreateInstallment(enrollmentId: Int, amount: Int, dueDate: String) {
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@StudentProfileActivity, getString(R.string.installment_creating), Toast.LENGTH_SHORT).show()
                }
                val api = RetrofitClient.getInstance(this@StudentProfileActivity).create(InstallmentApi::class.java)
                val req = CreateInstallmentRequest(enrollmentId, amount, dueDate)
                val res = api.createInstallment(req)
                withContext(Dispatchers.Main) {
                    val msg = res.message.takeIf { it.isNotBlank() } ?: getString(R.string.installment_create_success)
                    Toast.makeText(this@StudentProfileActivity, msg, Toast.LENGTH_LONG).show()
                    CacheManager.clear(this@StudentProfileActivity, "student_installments_" + studentId)
                    fetchInstallments()
                    fetchFullData()
                }
            } catch (e: Exception) {
                if (e is kotlinx.coroutines.CancellationException) throw e
                withContext(Dispatchers.Main) {
                    val detail = extractServerDetail(e) ?: e.message ?: getString(R.string.common_unknown_error)
                    Toast.makeText(this@StudentProfileActivity, getString(R.string.common_err_with_detail, detail), Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    // ———————————————— A1: Adapter ————————————————
    inner class InstallmentAdapter(
        private var items: List<StudentInstallmentItem>,
        private val onPay: (StudentInstallmentItem) -> Unit,
        private val onRemind: (StudentInstallmentItem) -> Unit
    ) : RecyclerView.Adapter<InstallmentAdapter.VH>() {
        inner class VH(view: View) : RecyclerView.ViewHolder(view) {
            val tvCourse: TextView = view.findViewById(R.id.tvInstallmentCourse)
            val tvAmount: TextView = view.findViewById(R.id.tvInstallmentAmount)
            val tvDue: TextView = view.findViewById(R.id.tvInstallmentDue)
            val tvStatus: TextView = view.findViewById(R.id.tvInstallmentStatus)
            val tvPaidAt: TextView = view.findViewById(R.id.tvInstallmentPaidAt)
            val layoutActions: View = view.findViewById(R.id.layoutInstallmentActions)
            val btnPay: MaterialButton = view.findViewById(R.id.btnInstallmentPay)
            val btnRemind: MaterialButton = view.findViewById(R.id.btnInstallmentRemind)
        }
        override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
            val v = LayoutInflater.from(parent.context).inflate(R.layout.item_installment, parent, false)
            return VH(v)
        }
        override fun getItemCount(): Int = items.size
        override fun onBindViewHolder(holder: VH, position: Int) {
            val item = items[position]
            holder.tvCourse.text = item.course_title
            holder.tvAmount.text = holder.itemView.context.getString(R.string.common_toman_format, item.amount)
            holder.tvDue.text = holder.itemView.context.getString(R.string.installment_due, item.due_date)
            if (item.is_paid) {
                holder.tvStatus.text = holder.itemView.context.getString(R.string.installment_paid_label)
                holder.tvStatus.setTextColor(UiColors.resolve(holder.itemView.context, R.color.status_success))
                holder.tvPaidAt.visibility = View.VISIBLE
                holder.tvPaidAt.text = holder.itemView.context.getString(R.string.profile_inst_paidat, item.paid_at)
                holder.layoutActions.visibility = View.GONE
            } else {
                val overdue = JalaliUtils.isBeforeToday(item.due_date)
                holder.tvStatus.text = if (overdue) holder.itemView.context.getString(R.string.profile_inst_overdue) else holder.itemView.context.getString(R.string.profile_inst_pending)
                holder.tvStatus.setTextColor(if (overdue) UiColors.resolve(holder.itemView.context, R.color.status_danger) else UiColors.resolve(holder.itemView.context, R.color.status_warning))
                holder.tvPaidAt.visibility = View.GONE
                // FIX (گروه۳/آیتم۱۴): «پرداخت» و «یادآوری» قسط اکشن مالی ادمین/منشی‌اند؛
                // برای معلم ردیف قسط فقط خواندنی می‌ماند (isTeacherUser از Activity بیرونی).
                if (isTeacherUser) {
                    holder.layoutActions.visibility = View.GONE
                } else {
                    holder.layoutActions.visibility = View.VISIBLE
                    holder.btnPay.setOnClickListener { onPay(item) }
                    holder.btnRemind.setOnClickListener { onRemind(item) }
                }
            }
        }
        fun update(newList: List<StudentInstallmentItem>) {
            items = newList
            notifyDataSetChanged()
        }
    }

    private fun sendPortalLinkToParent() {
        val retrofit = RetrofitClient.getInstance(this)
        val api = retrofit.create(ProfileApi::class.java)

        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.

        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val res = api.sendPortalLink(studentId)
                withContext(Dispatchers.Main) {
                    com.google.android.material.snackbar.Snackbar.make(
                        findViewById(android.R.id.content),
                        getString(R.string.common_ok_msg, res.message),
                        com.google.android.material.snackbar.Snackbar.LENGTH_LONG
                    ).show()
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@StudentProfileActivity, getString(R.string.profile_portal_error), Toast.LENGTH_LONG).show()
                }
            }
        }
    }
}
