package com.example.kharazmiadmin

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.google.android.material.button.MaterialButton
import com.google.android.material.floatingactionbutton.FloatingActionButton
import com.google.android.material.tabs.TabLayout
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import retrofit2.HttpException
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Body
import retrofit2.http.Query
import retrofit2.http.Path
import java.util.Locale

interface TeacherManagementApi {
    @POST("/admin/teachers/{teacher_id}/suspend")
    suspend fun suspendTeacher(@Path("teacher_id") teacherId: Int): SuspendResponse

    @DELETE("/admin/teachers/{teacher_id}")
    suspend fun deleteTeacher(@Path("teacher_id") teacherId: Int): SimpleResponse
}

data class SettlementEditRequest(val total_amount: Long? = null, val reason: String)
interface SettlementSafetyApi {
    @POST("teachers/{teacher_id}/settlements/{settlement_id}/reverse")
    suspend fun reverseSettlement(@Path("teacher_id") teacherId: Int, @Path("settlement_id") settlementId: Int, @Query("reason") reason: String): SimpleResponse
    @PUT("teachers/{teacher_id}/settlements/{settlement_id}/edit")
    suspend fun editSettlement(@Path("teacher_id") teacherId: Int, @Path("settlement_id") settlementId: Int, @Body request: SettlementEditRequest): SimpleResponse
}

class TeacherProfileActivity : BaseActivity() {

    private var teacherId: Int = -1
    private var teacherMobile: String = ""
    private lateinit var rvClasses: RecyclerView
    private lateinit var classAdapter: ProfileClassAdapter
    private lateinit var tabLayoutTeacher: TabLayout

    // کانتینرهای تب‌ها
    private lateinit var llStatsContainer: LinearLayout
    private lateinit var llSettlementContainer: LinearLayout
    private lateinit var llCommunicationContainer: LinearLayout
    private lateinit var rvCommunicationHistory: RecyclerView
    private lateinit var tvCommunicationEmpty: TextView
    private var isSecretary: Boolean = false

    // کارهای تسویه‌حساب
    private lateinit var tvPendingSettlementSum: TextView
    private lateinit var btnSubmitSettlement: MaterialButton
    private lateinit var rvPendingSettlementSessions: RecyclerView
    private lateinit var rvSettlementHistory: RecyclerView
    private var pendingSessionIds: List<Int> = emptyList()

    // خلاصه همکاری - فقط admin
    private lateinit var cardCollaborationSummary: View
    private lateinit var tvCollabAvgDelay: TextView
    private lateinit var tvCollabLiveCount: TextView
    private lateinit var tvCollabSettlements: TextView
    private lateinit var tvCollabAutoEnded: TextView
    private lateinit var tvCollabPeriod: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_teacher_profile)

        teacherId = intent.getIntExtra("TEACHER_ID", -1)

        initViews()
        setupTabs()
        if (
            intent.getBooleanExtra("OPEN_SETTLEMENT_TAB", false) &&
            !isSecretary &&
            tabLayoutTeacher.tabCount > 1
        ) {
            tabLayoutTeacher.getTabAt(1)?.select()
        }

        // دکمه تماس
        findViewById<MaterialButton>(R.id.btnCallTeacher).setOnClickListener {
            if (teacherMobile.isNotEmpty()) {
                val intent = Intent(Intent.ACTION_DIAL, Uri.parse("tel:$teacherMobile"))
                startActivity(intent)
            }
        }

        // --- دکمه تعلیق معلم ---
        findViewById<MaterialButton>(R.id.btnSuspendTeacher).setOnClickListener {
            suspendTeacher()
        }

        // --- دکمه حذف معلم ---
        findViewById<MaterialButton>(R.id.btnDeleteTeacher).setOnClickListener {
            deleteTeacher()
        }

        // --- دکمه ویرایش (اتصال به EditTeacherActivity) ---
        findViewById<FloatingActionButton>(R.id.fabEditTeacher).setOnClickListener {
            val intent = Intent(this, EditTeacherActivity::class.java)
            intent.putExtra("TEACHER_ID", teacherId)
            startActivity(intent)
        }

        // دکمه تسویه نهایی مبالغ معلم
        btnSubmitSettlement.setOnClickListener {
            if (pendingSessionIds.isEmpty()) {
                Toast.makeText(this, getString(R.string.tprof_no_unsettled), Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }
            showSettlementConfirmationDialog()
        }

        // Setup RecyclerView for classes
        rvClasses = findViewById(R.id.rvClassList)
        rvClasses.layoutManager = LinearLayoutManager(this)
        classAdapter = ProfileClassAdapter(emptyList()) { classItem ->
            val intent = Intent(this, ClassDetailActivity::class.java)
            intent.putExtra("CLASS_ID", classItem.id)
            startActivity(intent)
        }
        rvClasses.adapter = classAdapter
    }

    private fun initViews() {
        tabLayoutTeacher = findViewById(R.id.tabLayoutTeacher)
        llStatsContainer = findViewById(R.id.llStatsContainer)
        llSettlementContainer = findViewById(R.id.llSettlementContainer)
        llCommunicationContainer = findViewById(R.id.llTeacherCommunicationContainer)
        rvCommunicationHistory = findViewById(R.id.rvTeacherCommunicationHistory)
        tvCommunicationEmpty = findViewById(R.id.tvTeacherCommunicationEmpty)
        rvCommunicationHistory.layoutManager = LinearLayoutManager(this)
        rvCommunicationHistory.isNestedScrollingEnabled = false

        tvPendingSettlementSum = findViewById(R.id.tvPendingSettlementSum)
        btnSubmitSettlement = findViewById(R.id.btnSubmitSettlement)
        
        rvPendingSettlementSessions = findViewById(R.id.rvPendingSettlementSessions)
        rvPendingSettlementSessions.layoutManager = LinearLayoutManager(this)
        
        rvSettlementHistory = findViewById(R.id.rvSettlementHistory)
        rvSettlementHistory.layoutManager = LinearLayoutManager(this)

        cardCollaborationSummary = findViewById(R.id.cardCollaborationSummary)
        tvCollabAvgDelay = findViewById(R.id.tvCollabAvgDelay)
        tvCollabLiveCount = findViewById(R.id.tvCollabLiveCount)
        tvCollabSettlements = findViewById(R.id.tvCollabSettlements)
        tvCollabAutoEnded = findViewById(R.id.tvCollabAutoEnded)
        tvCollabPeriod = findViewById(R.id.tvCollabPeriod)
    }

    private fun setupTabs() {
        // منشی ارتباطات را می‌بیند، اما تب مالی تسویه برای او حذف می‌ماند.
        val credsPrefs = getSharedPreferences("UserCreds", Context.MODE_PRIVATE)
        val subRole = credsPrefs.getString("USER_SUB_ROLE", "admin") ?: "admin"
        isSecretary = subRole == "secretary"
        if (isSecretary) {
            tabLayoutTeacher.removeTabAt(1)
        }

        tabLayoutTeacher.addOnTabSelectedListener(object : TabLayout.OnTabSelectedListener {
            override fun onTabSelected(tab: TabLayout.Tab?) {
                when {
                    tab?.position == 0 -> {
                        showTeacherTab(llStatsContainer)
                        fetchData()
                    }
                    isSecretary && tab?.position == 1 -> {
                        showTeacherTab(llCommunicationContainer)
                        fetchCommunicationHistory()
                    }
                    !isSecretary && tab?.position == 1 -> {
                        showTeacherTab(llSettlementContainer)
                        fetchSettlementData()
                    }
                    !isSecretary && tab?.position == 2 -> {
                        showTeacherTab(llCommunicationContainer)
                        fetchCommunicationHistory()
                    }
                }
            }
            override fun onTabUnselected(tab: TabLayout.Tab?) {}
            override fun onTabReselected(tab: TabLayout.Tab?) {
                val communicationPosition = if (isSecretary) 1 else 2
                if (tab?.position == communicationPosition) fetchCommunicationHistory()
            }
        })
    }

    override fun onResume() {
        super.onResume()
        if (teacherId != -1) {
            val selected = tabLayoutTeacher.selectedTabPosition
            val communicationPosition = if (isSecretary) 1 else 2
            when {
                selected == 0 -> fetchData()
                selected == communicationPosition -> fetchCommunicationHistory()
                else -> fetchSettlementData()
            }
        }
    }

    private fun showTeacherTab(visibleContainer: View) {
        llStatsContainer.visibility =
            if (visibleContainer === llStatsContainer) View.VISIBLE else View.GONE
        llSettlementContainer.visibility =
            if (visibleContainer === llSettlementContainer) View.VISIBLE else View.GONE
        llCommunicationContainer.visibility =
            if (visibleContainer === llCommunicationContainer) View.VISIBLE else View.GONE
    }

    private fun fetchCommunicationHistory() {
        tvCommunicationEmpty.visibility = View.VISIBLE
        tvCommunicationEmpty.text = getString(R.string.profile_comm_loading)
        rvCommunicationHistory.visibility = View.GONE

        val api = RetrofitClient.getInstance(this).create(ProfileApi::class.java)
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val history = api.getTeacherCommunicationHistory(teacherId)
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

    private fun fetchData() {
        val retrofit = RetrofitClient.getInstance(this)
        val profileApi = retrofit.create(ProfileApi::class.java)
        val teacherPanelApi = retrofit.create(TeacherPanelApi::class.java)

        val cacheKey = "teacher_full_profile_" + teacherId
        val type = object : com.google.gson.reflect.TypeToken<FullTeacherProfile>() {}.type

        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.

        lifecycleScope.launch(Dispatchers.Main) {
            CachedApiCall.execute(
                context = this@TeacherProfileActivity,
                cacheKey = cacheKey,
                type = type,
                networkCall = { profileApi.getFullTeacherProfile(teacherId) },
                onSuccess = { data, isOffline, timestamp ->
                    // پر کردن هدر
                    // FIX(null-data): فیلدهای legacy ممکن است null باشند — فال‌بک امن در نمایش.
                    val codeStr = if (data.info.teacher_code != null) getString(R.string.tprof_code, data.info.teacher_code) else ""
                    findViewById<TextView>(R.id.tvTeacherName).text = "${data.info.name ?: ""}$codeStr"
                    findViewById<TextView>(R.id.tvTeacherPhone).text = data.info.mobile ?: ""
                    teacherMobile = data.info.mobile ?: ""

                    // بارگذاری عکس پروفایل با Glide
                    val profileImg = findViewById<android.widget.ImageView>(R.id.imgTeacherProfile)
                    if (profileImg != null) {
                        if (!data.info.profile_image.isNullOrEmpty()) {
                            val baseUrl = RetrofitClient.getInstance(this@TeacherProfileActivity).baseUrl().toString()
                            val imgUrl = baseUrl + "uploads/profiles/" + data.info.profile_image
                            val glideAuthToken = SecureLoginStore.getToken(this@TeacherProfileActivity)  // FIX M22.
                            // FIX M3: Glide با هدر احراز (اندپوینت /uploads دیگر عمومی نیست).
                            val glideUrl = com.bumptech.glide.load.model.GlideUrl(
                                imgUrl,
                                com.bumptech.glide.load.model.LazyHeaders.Builder()
                                    .addHeader("Authorization", "Bearer $glideAuthToken")
                                    .build()
                            )
                            com.bumptech.glide.Glide.with(this@TeacherProfileActivity)
                                .load(glideUrl)
                                .placeholder(android.R.drawable.sym_def_app_icon)
                                .error(android.R.drawable.sym_def_app_icon)
                                .circleCrop()
                                .into(profileImg)
                        } else {
                            profileImg.setImageDrawable(AvatarHelper.getAvatar(this@TeacherProfileActivity, data.info.name ?: "", teacherId))
                        }
                    }

                    // پر کردن کارت‌های آمار همراه با فرمت محلی امن
                    findViewById<TextView>(R.id.tvRevenue).text = String.format(java.util.Locale.US, "%,d", data.total_revenue)
                    findViewById<TextView>(R.id.tvStudentCount).text = data.total_students.toString()
                    findViewById<TextView>(R.id.tvClassCount).text = data.active_classes_count.toString()

                    // خلاصه همکاری - فقط برای admin و اگر داده موجود باشد
                    val prefsCollab = getSharedPreferences("UserCreds", Context.MODE_PRIVATE)
                    val roleCollab = prefsCollab.getString("USER_SUB_ROLE", "admin") ?: "admin"
                    if (roleCollab == "admin") {
                        data.collaborationSummary?.let { collab ->
                            cardCollaborationSummary.visibility = View.VISIBLE
                            tvCollabAvgDelay.text = getString(R.string.tprof_delay, collab.averageDelayMinutes, collab.delaySamplesCount)
                            tvCollabLiveCount.text = getString(R.string.tprof_live, collab.liveSessionsLast30Days)
                            tvCollabSettlements.text = getString(R.string.tprof_settlements, collab.totalSettlementsCount, String.format(Locale("en", "US"), "%,d", collab.totalSettledAmount))
                            tvCollabAutoEnded.text = getString(R.string.tprof_autoend, collab.autoEndedSessionsCount, collab.autoEndedLast30DaysCount)
                            tvCollabPeriod.text = getString(R.string.tprof_period, collab.periodStart, collab.periodEnd)
                        } ?: run {
                            // اگر full_profile شامل خلاصه نبود (مثلاً cache قدیمی)، از endpoint جدا بگیر
                            cardCollaborationSummary.visibility = View.GONE
                            fetchCollaborationSummary()
                        }
                    } else {
                        cardCollaborationSummary.visibility = View.GONE
                    }

                    // آپدیت لیست کلاس‌ها به موازات
                    // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
                    lifecycleScope.launch(Dispatchers.IO) {
                        try {
                            val classes = teacherPanelApi.getMyClasses(teacherId)
                            withContext(Dispatchers.Main) {
                                classAdapter.updateList(classes)
                            }
                        } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                            // آفلاین
                        }
                    }

                    if (isOffline) {
                        CachedApiCall.showOfflineBanner(this@TeacherProfileActivity, timestamp)
                    } else {
                        CachedApiCall.hideOfflineBanner(this@TeacherProfileActivity)
                    }
                },
                onFailure = {
                    Toast.makeText(this@TeacherProfileActivity, getString(R.string.common_offline_empty), Toast.LENGTH_LONG).show()
                }
            )
        }
    }

    // واکشی دیتای تسویه‌حساب معلمان همراه با کش محلی کلاینت‌ساید
    private fun fetchSettlementData() {
        val retrofit = RetrofitClient.getInstance(this)
        val api = retrofit.create(ProfileApi::class.java)

        val cacheKeyPending = "teacher_pending_settlement_" + teacherId
        val typePending = object : com.google.gson.reflect.TypeToken<TeacherPendingSettlementResponse>() {}.type

        // نسخه‌گذاری کش برای کنار گذاشتن history قدیمی که ممکن است شناسهٔ settlement
        // متعلق به رکورد/معلم دیگری را نگه داشته باشد و عملیات را 404 کند.
        val cacheKeyHistory = "teacher_settlement_history_v2_" + teacherId
        val typeHistory = object : com.google.gson.reflect.TypeToken<List<SettlementHistoryItem>>() {}.type

        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.

        lifecycleScope.launch(Dispatchers.Main) {
            // 1. دریافت جلسات تسویه نشده
            CachedApiCall.execute(
                context = this@TeacherProfileActivity,
                cacheKey = cacheKeyPending,
                type = typePending,
                networkCall = { api.getPendingSettlement(teacherId) },
                onSuccess = { data, isOffline, timestamp ->
                    tvPendingSettlementSum.text = getString(R.string.tprof_pending, String.format(Locale("en", "US"), "%,d", data.total_amount))
                    pendingSessionIds = data.pending_sessions.map { it.session_id }
                    
                    rvPendingSettlementSessions.adapter = PendingSessionsAdapter(data.pending_sessions)

                    if (isOffline) {
                        CachedApiCall.showOfflineBanner(this@TeacherProfileActivity, timestamp)
                    } else {
                        CachedApiCall.hideOfflineBanner(this@TeacherProfileActivity)
                    }
                },
                onFailure = {
                    tvPendingSettlementSum.text = getString(R.string.tprof_zero)
                    pendingSessionIds = emptyList()
                    rvPendingSettlementSessions.adapter = null
                }
            )

            // 2. دریافت تاریخچه تسویه‌ها
            CachedApiCall.execute(
                context = this@TeacherProfileActivity,
                cacheKey = cacheKeyHistory,
                type = typeHistory,
                networkCall = { api.getSettlementHistory(teacherId) },
                onSuccess = { history, _, _ ->
                    rvSettlementHistory.adapter = SettlementHistoryAdapter(history,
                        onReverse = { item -> reverseSettlement(item) },
                        onEdit = { item -> editSettlement(item) })
                },
                onFailure = {
                    rvSettlementHistory.adapter = null
                }
            )
        }
    }

    private fun settlementError(action: String, error: Exception): String {
        if (error is HttpException) {
            val body = error.response()?.errorBody()?.string().orEmpty()
            val detail = try {
                org.json.JSONObject(body).optString("detail")
            } catch (_: Exception) { "" }
            return "$action ناموفق بود (HTTP ${error.code()})" + if (detail.isNotBlank()) ": $detail" else ""
        }
        return "$action ناموفق بود: ${error.message ?: "خطای شبکه"}"
    }

    private fun reverseSettlement(item: SettlementHistoryItem) {
        AlertDialog.Builder(this)
            .setTitle("برگشت امن تسویه")
            .setMessage("این عملیات سند برگشت ثبت می‌کند و کیف بدهی دانش‌آموز را تغییر نمی‌دهد.")
            .setPositiveButton("ثبت برگشت") { _, _ ->
                lifecycleScope.launch(Dispatchers.IO) {
                    try {
                        RetrofitClient.getInstance(this@TeacherProfileActivity).create(SettlementSafetyApi::class.java)
                            .reverseSettlement(teacherId, item.operationId, "اصلاح مالی توسط ادمین")
                        withContext(Dispatchers.Main) {
                            CacheManager.clear(this@TeacherProfileActivity, "teacher_settlement_history_v2_$teacherId")
                            CacheManager.clear(this@TeacherProfileActivity, "teacher_settlement_history_$teacherId")
                            fetchSettlementData()
                        }
                    } catch (error: Exception) {
                        if (error is kotlinx.coroutines.CancellationException) throw error
                        withContext(Dispatchers.Main) {
                            Toast.makeText(this@TeacherProfileActivity, settlementError("برگشت تسویه", error), Toast.LENGTH_LONG).show()
                        }
                    }
                }
            }
            .setNegativeButton("انصراف", null).show()
    }

    private fun editSettlement(item: SettlementHistoryItem) {
        val input = android.widget.EditText(this)
        input.hint = "مبلغ تعدیل جدید"
        AlertDialog.Builder(this).setTitle("تعدیل امن تسویه").setView(input)
            .setPositiveButton("ثبت تعدیل") { _, _ ->
                val amount = input.text.toString().toLongOrNull()
                lifecycleScope.launch(Dispatchers.IO) {
                    try {
                        RetrofitClient.getInstance(this@TeacherProfileActivity).create(SettlementSafetyApi::class.java)
                            .editSettlement(teacherId, item.operationId, SettlementEditRequest(amount, "تعدیل مالی توسط ادمین"))
                        withContext(Dispatchers.Main) {
                            CacheManager.clear(this@TeacherProfileActivity, "teacher_settlement_history_v2_$teacherId")
                            CacheManager.clear(this@TeacherProfileActivity, "teacher_settlement_history_$teacherId")
                            fetchSettlementData()
                        }
                    } catch (error: Exception) {
                        if (error is kotlinx.coroutines.CancellationException) throw error
                        withContext(Dispatchers.Main) {
                            Toast.makeText(this@TeacherProfileActivity, settlementError("تعدیل تسویه", error), Toast.LENGTH_LONG).show()
                        }
                    }
                }
            }.setNegativeButton("انصراف", null).show()
    }

    private fun showSettlementConfirmationDialog() {
        val count = pendingSessionIds.size
        val amountText = tvPendingSettlementSum.text.toString()

        AlertDialog.Builder(this)
            .setTitle(getString(R.string.tprof_settle_title))
            .setMessage(getString(R.string.tprof_settle_msg, amountText, count))
            .setPositiveButton(getString(R.string.tprof_settle_yes)) { _, _ ->
                performSettlement()
            }
            .setNegativeButton(getString(R.string.common_cancel), null)
            .show()
    }

    private fun performSettlement() {
        val retrofit = RetrofitClient.getInstance(this)
        val api = retrofit.create(ProfileApi::class.java)
        // FIX (F-D3): گارد دابل‌کلیک — دکمه تا پایان درخواست غیرفعال (سرور هم بک‌استاپ دارد ولی UX بهتر است).
        btnSubmitSettlement.isEnabled = false

        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.

        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val res = api.settleTeacherSessions(teacherId, SettleRequest(pendingSessionIds))
                withContext(Dispatchers.Main) {
                    // ابطال کامل کش پروفایل و تسویه‌حساب معلم
                    CacheManager.clear(this@TeacherProfileActivity, "teacher_full_profile_$teacherId")
                    CacheManager.clear(this@TeacherProfileActivity, "teacher_pending_settlement_$teacherId")
                    CacheManager.clear(this@TeacherProfileActivity, "teacher_settlement_history_v2_$teacherId")
                    CacheManager.clear(this@TeacherProfileActivity, "teacher_settlement_history_$teacherId")
                    CacheManager.clearByPrefix(this@TeacherProfileActivity, "person_list_TEACHER")
                    CacheManager.clearByPrefix(this@TeacherProfileActivity, "today_summary_admin_")

                    // رفرش لیست
                    fetchSettlementData()

                    // بازخورد لمسی (Haptic Feedback) برای تایید نهایی تسویه حساب
                    window.decorView.performHapticFeedback(android.view.HapticFeedbackConstants.VIRTUAL_KEY)

                    // نمایش دیالوگ تایید بصری بسیار شیک به جای توست خشک
                    val dialogView = LayoutInflater.from(this@TeacherProfileActivity).inflate(R.layout.dialog_remittance_success, null)
                    
                    val imgSuccessIcon = dialogView.findViewById<ImageView>(R.id.imgSuccessIcon)
                    if (imgSuccessIcon != null) {
                        imgSuccessIcon.alpha = 0f
                        imgSuccessIcon.scaleX = 0f
                        imgSuccessIcon.scaleY = 0f
                        imgSuccessIcon.animate()
                            .alpha(1f)
                            .scaleX(1f)
                            .scaleY(1f)
                            .setDuration(AnimationConstants.ANIM_TRANSITION)
                            .setInterpolator(android.view.animation.OvershootInterpolator())
                            .start()
                    }

                    val dialog = AlertDialog.Builder(this@TeacherProfileActivity)
                        .setView(dialogView)
                        .create()

                    dialogView.findViewById<TextView>(R.id.tvSuccessMessage).text = 
                        getString(R.string.tprof_receipt, res.settlement_id, String.format(Locale("en", "US"), "%,d", res.total_amount), res.session_count)
                    dialogView.findViewById<TextView>(R.id.tvSuccessMessage).gravity = android.view.Gravity.CENTER

                    dialogView.findViewById<com.google.android.material.button.MaterialButton>(R.id.btnPrintRemittance).visibility = View.GONE
                    dialogView.findViewById<com.google.android.material.button.MaterialButton>(R.id.btnSaveAsPdf).visibility = View.GONE
                    // FIX (گروه۳/آیتم۱۰): این پاپ‌آپ لی‌اوت مشترک «ثبت حواله» را inflate می‌کند،
                    // ولی اینجا **تسویهٔ حساب معلم** است نه پرداخت دانش‌آموز ⇒ دکمهٔ
                    // «ثبت مجدد برای دانش‌آموز دیگر» بی‌معنا بود (و در این مسیر listener هم نداشت ⇒
                    // کلیکش هیچ کاری نمی‌کرد). همان الگوی موجود در AttendanceActivity:813.
                    // دکمه فقط در مسیر ثبت حوالهٔ دانش‌آموز (InvoiceActivity) فعال می‌ماند.
                    dialogView.findViewById<com.google.android.material.button.MaterialButton>(R.id.btnRegisterAgain).visibility = View.GONE
                    
                    val btnClose = dialogView.findViewById<com.google.android.material.button.MaterialButton>(R.id.btnClose)
                    btnClose.text = getString(R.string.common_ok)
                    btnClose.setOnClickListener {
                        dialog.dismiss()
                    }
                    dialog.show()
                    btnSubmitSettlement.isEnabled = true // FIX (F-D3): پایان موفقیت‌آمیز
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    btnSubmitSettlement.isEnabled = true // FIX (F-D3): پایان با خطا — تلاش مجدد ممکن
                    Toast.makeText(this@TeacherProfileActivity, getString(R.string.tprof_settle_error), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun fetchCollaborationSummary() {
        val prefs = getSharedPreferences("UserCreds", Context.MODE_PRIVATE)
        val role = prefs.getString("USER_SUB_ROLE", "admin") ?: "admin"
        if (role != "admin") return
        val api = RetrofitClient.getInstance(this).create(ProfileApi::class.java)
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val collab = api.getTeacherCollaborationSummary(teacherId)
                withContext(Dispatchers.Main) {
                    cardCollaborationSummary.visibility = View.VISIBLE
                    tvCollabAvgDelay.text = getString(R.string.tprof_delay, collab.averageDelayMinutes, collab.delaySamplesCount)
                    tvCollabLiveCount.text = getString(R.string.tprof_live, collab.liveSessionsLast30Days)
                    tvCollabSettlements.text = getString(R.string.tprof_settlements, collab.totalSettlementsCount, String.format(Locale("en", "US"), "%,d", collab.totalSettledAmount))
                    tvCollabAutoEnded.text = getString(R.string.tprof_autoend, collab.autoEndedSessionsCount, collab.autoEndedLast30DaysCount)
                    tvCollabPeriod.text = getString(R.string.tprof_period, collab.periodStart, collab.periodEnd)
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    cardCollaborationSummary.visibility = View.GONE
                }
            }
        }
    }

    private fun suspendTeacher() {
        if (teacherId == -1) return

        val retrofit = RetrofitClient.getInstance(this)
        val api = retrofit.create(TeacherManagementApi::class.java)

        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.

        lifecycleScope.launch(Dispatchers.Main) {
            try {
                val response = withContext(Dispatchers.IO) { api.suspendTeacher(teacherId) }
                Toast.makeText(this@TeacherProfileActivity, response.message, Toast.LENGTH_SHORT).show()

                CacheManager.clear(this@TeacherProfileActivity, "teacher_full_profile_$teacherId")
                CacheManager.clearByPrefix(this@TeacherProfileActivity, "person_list_TEACHER")

                fetchData()
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                Toast.makeText(this@TeacherProfileActivity, getString(R.string.tprof_suspend_error), Toast.LENGTH_SHORT).show()
                android.util.Log.e("TeacherProfileActivity", "suspendTeacher failed", e)
            }
        }
    }

    private fun deleteTeacher() {
        if (teacherId == -1) return

        AlertDialog.Builder(this)
            .setTitle(getString(R.string.tprof_del_title))
            .setMessage(getString(R.string.tprof_del_msg))
            .setPositiveButton(getString(R.string.common_delete_yes)) { dialog, _ ->
                performDeleteTeacher()
                dialog.dismiss()
            }
            .setNegativeButton(getString(R.string.common_cancel)) { dialog, _ ->
                dialog.dismiss()
            }
            .show()
    }

    private fun performDeleteTeacher() {
        val retrofit = RetrofitClient.getInstance(this)
        val api = retrofit.create(TeacherManagementApi::class.java)

        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.

        lifecycleScope.launch(Dispatchers.Main) {
            try {
                val response = withContext(Dispatchers.IO) { api.deleteTeacher(teacherId) }
                Toast.makeText(this@TeacherProfileActivity, response.message, Toast.LENGTH_SHORT).show()

                CacheManager.clear(this@TeacherProfileActivity, "teacher_full_profile_$teacherId")
                CacheManager.clearByPrefix(this@TeacherProfileActivity, "person_list_TEACHER")

                finish()
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                Toast.makeText(this@TeacherProfileActivity, getString(R.string.tprof_del_error, e.message), Toast.LENGTH_LONG).show()
                android.util.Log.e("TeacherProfileActivity", "performDeleteTeacher failed", e)
            }
        }
    }
}

// آداپتور لیست کلاس‌ها
class ProfileClassAdapter(
    private var classes: List<TeacherClassItem>,
    private val onClassClick: (TeacherClassItem) -> Unit
) : RecyclerView.Adapter<ProfileClassAdapter.ClassViewHolder>() {

    fun updateList(newList: List<TeacherClassItem>) {
        classes = newList
        notifyDataSetChanged()
    }

    class ClassViewHolder(view: View) : RecyclerView.ViewHolder(view) {
        val tvClassName: TextView = view.findViewById(R.id.tvClassName)
        val tvClassCode: TextView = view.findViewById(R.id.tvClassCode)
        val tvClassStatus: TextView = view.findViewById(R.id.tvClassStatus)
        val tvClassDetails: TextView = view.findViewById(R.id.tvClassDetails)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ClassViewHolder {
        val view = LayoutInflater.from(parent.context)
            .inflate(R.layout.item_teacher_class, parent, false)
        return ClassViewHolder(view)
    }

    override fun onBindViewHolder(holder: ClassViewHolder, position: Int) {
        val classItem = classes[position]

        holder.tvClassName.text = classItem.title ?: ""
        holder.tvClassCode.text = holder.itemView.context.getString(R.string.tprof_class_code, classItem.code ?: "")
        holder.tvClassDetails.text = classItem.grade_level ?: ""

        when {
            classItem.is_suspended -> {
                holder.tvClassStatus.text = holder.itemView.context.getString(R.string.tprof_suspended)
                holder.tvClassStatus.setTextColor(UiColors.resolve(holder.itemView.context, R.color.status_warning))
            }
            !classItem.is_admin_approved -> {
                holder.tvClassStatus.text = holder.itemView.context.getString(R.string.tprof_pending2)
                holder.tvClassStatus.setTextColor(UiColors.resolve(holder.itemView.context, R.color.status_info))
            }
            else -> {
                holder.tvClassStatus.text = holder.itemView.context.getString(R.string.tprof_active)
                holder.tvClassStatus.setTextColor(UiColors.resolve(holder.itemView.context, R.color.status_success))
            }
        }

        holder.itemView.setOnClickListener {
            onClassClick(classItem)
        }
    }

    override fun getItemCount() = classes.size
}

// آداپتور جلسات تسویه نشده
class PendingSessionsAdapter(private val list: List<PendingSettlementSession>) : RecyclerView.Adapter<PendingSessionsAdapter.VH>() {
    class VH(v: View) : RecyclerView.ViewHolder(v) {
        val tvClassTitle: TextView = v.findViewById(R.id.tvClassTitle)
        val tvSessionDate: TextView = v.findViewById(R.id.tvSessionDate)
        val tvSessionAmount: TextView = v.findViewById(R.id.tvSessionAmount)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val v = LayoutInflater.from(parent.context).inflate(R.layout.item_pending_settlement_session, parent, false)
        return VH(v)
    }

    override fun onBindViewHolder(holder: VH, position: Int) {
        val item = list[position]
        // FIX(null-data): class_title/date legacy ممکن است null باشند — فال‌بک امن + تله‌ی نهایی:
        // یک رکورد ناقص نباید کل RecyclerView تسویه را crash کند.
        try {
            val codeStr = if (item.session_code != null) holder.itemView.context.getString(R.string.tprof_code2, item.session_code) else ""
            holder.tvClassTitle.text = holder.itemView.context.getString(R.string.tprof_row, item.class_title ?: "", codeStr, item.present_count)
            // FIX(undated-sessions): سرور برای جلسه‌ی بدون تاریخ "" برمی‌گرداند (هیچ تاریخ جعلی‌ای
            // ساخته نمی‌شود) — به‌جای خط خالی، «تاریخ نامشخص» نمایش داده می‌شود.
            val sessionDate = item.date?.takeIf { it.isNotBlank() }
            holder.tvSessionDate.text = if (sessionDate != null) {
                holder.itemView.context.getString(R.string.tprof_date, sessionDate)
            } else {
                holder.itemView.context.getString(R.string.tprof_date_unknown)
            }
            val amt = item.amount ?: 0L
            holder.tvSessionAmount.text = holder.itemView.context.getString(R.string.portal_money, String.format(java.util.Locale.US, "%,d", amt))
        } catch (e: Exception) {
            android.util.Log.e("PendingSessionsAdapter", "Error binding row ${item.session_id}", e)
        }
    }

    override fun getItemCount() = list.size
}

// آداپتور تاریخچه تسویه‌ها
class SettlementHistoryAdapter(
    private val list: List<SettlementHistoryItem>,
    private val onReverse: (SettlementHistoryItem) -> Unit,
    private val onEdit: (SettlementHistoryItem) -> Unit
) : RecyclerView.Adapter<SettlementHistoryAdapter.VH>() {
    class VH(v: View) : RecyclerView.ViewHolder(v) {
        val tvSettledAmount: TextView = v.findViewById(R.id.tvSettledAmount)
        val tvSettlementDocument: TextView = v.findViewById(R.id.tvSettlementDocument)
        val tvSettledDate: TextView = v.findViewById(R.id.tvSettledDate)
        val tvSessionCount: TextView = v.findViewById(R.id.tvSessionCount)
        val btnReverseSettlement: View = v.findViewById(R.id.btnReverseSettlement)
        val btnEditSettlement: View = v.findViewById(R.id.btnEditSettlement)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val v = LayoutInflater.from(parent.context).inflate(R.layout.item_settlement_history, parent, false)
        return VH(v)
    }

    override fun onBindViewHolder(holder: VH, position: Int) {
        val item = list[position]
        // FIX(null-data): فال‌بک امن برای رکوردهای legacy ناقص + تله‌ی نهایی (یک رکورد کل لیست را نمی‌شکند).
        try {
            val amt = item.total_amount ?: 0L
            holder.tvSettledAmount.text = holder.itemView.context.getString(R.string.portal_money, String.format(java.util.Locale.US, "%,d", amt))
            holder.tvSettlementDocument.text = "سند تسویه #${item.operationId} | ${if (item.is_reversed) "برگشت‌خورده" else "فعال"}" +
                (item.reversal_reason?.let { " | علت: $it" } ?: "")
            holder.tvSettledDate.text = holder.itemView.context.getString(R.string.tprof_settled_date, item.settled_at ?: "")
            holder.tvSessionCount.text = holder.itemView.context.getString(R.string.tprof_sessions, item.session_count)
            holder.btnReverseSettlement.visibility = if (item.is_reversed) View.GONE else View.VISIBLE
            holder.btnEditSettlement.visibility = if (item.is_reversed) View.GONE else View.VISIBLE
            holder.btnReverseSettlement.setOnClickListener { onReverse(item) }
            holder.btnEditSettlement.setOnClickListener { onEdit(item) }
        } catch (e: Exception) {
            android.util.Log.e("SettlementHistoryAdapter", "Error binding row ${item.id}", e)
        }
    }

    override fun getItemCount() = list.size
}
