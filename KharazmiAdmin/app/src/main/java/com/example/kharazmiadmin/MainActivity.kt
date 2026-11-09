package com.example.kharazmiadmin

import android.content.Context
import android.content.Intent
import android.graphics.Color
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.LayoutInflater
import android.view.View
import android.view.animation.DecelerateInterpolator
import android.widget.ImageView
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.lifecycle.lifecycleScope
import androidx.core.view.GravityCompat
import androidx.drawerlayout.widget.DrawerLayout
import com.google.android.material.navigation.NavigationView
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

// ==========================================
// API Definitions
// ==========================================
interface DashboardSettingsApi {
    @GET("admin/institute_settings")
    suspend fun getSettings(): SettingsResponse
}

interface DeletedClassesApi {
    // FIX(archive): مدل درست آرشیو (ArchivedClassItem) + جست‌وجو + جزئیات کنترول‌شده.
    @GET("admin/deleted_classes")
    suspend fun getDeletedClasses(
        @Query("query") query: String? = null,
        @Query("title") title: String? = null,
        @Query("teacher") teacher: String? = null,
        @Query("code") code: String? = null,
        @Query("deleted_from") deletedFrom: String? = null,
        @Query("deleted_to") deletedTo: String? = null
    ): List<ArchivedClassItem>

    @GET("admin/deleted_classes/{id}")
    suspend fun getArchivedClassDetail(@Path("id") id: Int): ArchivedClassDetail

    // FIX(D1): بازیابی کلاس آرشیوشده — فقط متادیتا (سرور برای بازیابی کامل عمداً 400 می‌دهد).
    @POST("admin/deleted_classes/{id}/restore")
    suspend fun restoreArchivedClass(
        @Path("id") id: Int,
        @Body body: ClassRestoreRequest
    ): ClassRestoreResponse
}

interface MeApi {
    @GET("auth/me")
    suspend fun getMe(): MeResponse
}

data class MeResponse(
    val user_id: Int,
    val name: String,
    val role: String,
    val permissions: List<String>
)

data class SettingsResponse(
    val name: String,
    val logo_path: String?,
    val address: String,
    val phone: String,
    val official_email: String?,
    val footer_text: String? = null,
    val card_number: String? = null
)

class MainActivity : BaseActivity() {

    private lateinit var tvHeaderMainTitle: TextView
    private lateinit var tvHeaderShamsiDate: TextView
    private lateinit var tvHeaderLiveClock: TextView
    private lateinit var drawerLayout: DrawerLayout
    private var todaySummaryLoading = false
    private var dashboardSubRole: String = "admin"
    private var currentLateClasses: List<LateClassAlert> = emptyList()
    private var currentInstallmentAlerts: List<DueInstallmentAlert> = emptyList()
    private var currentTeacherSettlementAlerts: List<TeacherSettlementAlert> = emptyList()

    private val handler = Handler(Looper.getMainLooper())
    private val clockRunnable = object : Runnable {
        override fun run() {
            val calendar = java.util.Calendar.getInstance()
            val timeStr = String.format(java.util.Locale.US, "%02d:%02d", calendar.get(java.util.Calendar.HOUR_OF_DAY), calendar.get(java.util.Calendar.MINUTE))
            tvHeaderLiveClock.text = timeStr
            handler.postDelayed(this, 15000) // بروزرسانی هر ۱۵ ثانیه
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        // ۱. انتساب ویوها
        drawerLayout = findViewById(R.id.drawer_layout)
        tvHeaderMainTitle = findViewById(R.id.tvHeaderMainTitle)
        tvHeaderShamsiDate = findViewById(R.id.tvHeaderShamsiDate)
        tvHeaderLiveClock = findViewById(R.id.tvHeaderLiveClock)
        val navView = findViewById<NavigationView>(R.id.nav_view)

        // ۲. نمایش اطلاعات زنده هدر
        tvHeaderShamsiDate.text = getCurrentShamsiDate()
        handler.post(clockRunnable)

        // ۳. بررسی و اعمال محدودیت دسترسی منشی (Secretary)
        val credsPrefs = getSharedPreferences("UserCreds", Context.MODE_PRIVATE)
        val subRole = credsPrefs.getString("USER_SUB_ROLE", "admin") ?: "admin"
        dashboardSubRole = subRole
        
        if (subRole == "secretary") {
            val menu = navView.menu
            menu.findItem(R.id.nav_report)?.isVisible = false
            menu.findItem(R.id.nav_chart)?.isVisible = false
            menu.findItem(R.id.nav_pending)?.isVisible = false
            menu.findItem(R.id.nav_share_config)?.isVisible = false
            menu.findItem(R.id.nav_approve_class)?.isVisible = false
            menu.findItem(R.id.nav_deletion_requests)?.isVisible = false
            menu.findItem(R.id.nav_havale)?.isVisible = false
            menu.findItem(R.id.nav_institute_settings)?.isVisible = false
            menu.findItem(R.id.nav_deleted_classes)?.isVisible = false
            menu.findItem(R.id.nav_audit_radar)?.isVisible = false
            menu.findItem(R.id.nav_dunning)?.isVisible = false
            menu.findItem(R.id.nav_admin_dashboard)?.isVisible = false
        } else {
            // Audit Radar is admin-only - hide for non-admin implicitly handled, but explicitly ensure visible for admin
            navView.menu.findItem(R.id.nav_audit_radar)?.isVisible = true
            navView.menu.findItem(R.id.nav_dunning)?.isVisible = true
            navView.menu.findItem(R.id.nav_admin_dashboard)?.isVisible = true
        }

        // Audit Radar: ensure hidden for teachers (they don't have nav_view admin items but just in case)
        if (subRole == "teacher") {
            navView.menu.findItem(R.id.nav_audit_radar)?.isVisible = false
            navView.menu.findItem(R.id.nav_dunning)?.isVisible = false
            navView.menu.findItem(R.id.nav_admin_dashboard)?.isVisible = false
        }

        // ۴. اتصال آیکون‌های ۱۲ گانه جدید داشبورد
        setupMenuClickListeners(subRole)

        // ۵. انیمیشن باز شدن آیکون‌ها
        animateEntrance()

        // ۶. دریافت پویای نام آموزشگاه از تنظیمات مرکزی سرور
        fetchInstituteSettingsName()
        fetchPermissionsAndSyncUI()

        // ۷. نشانگر «کلاس‌های در حال برگزاری» در پیشخوان (نقطه قرمز اگر زنده باشد)
        fetchLiveSessionCount()

        // کارت وضعیت امروز با کش لحظه‌ای ۳۰ ثانیه‌ای؛ لمس عنوان، رفرش اجباری است.
        findViewById<TextView>(R.id.tvTodaySummaryTitle).setOnClickListener {
            fetchTodaySummary(forceRefresh = true)
        }

        // ۸. ناوبری کشویی (Drawer Navigation)
        findViewById<ImageView>(R.id.imgHeaderDashboardIcon).setOnClickListener {
            drawerLayout.openDrawer(GravityCompat.START)
        }

        navView.setNavigationItemSelectedListener { menuItem ->
            drawerLayout.closeDrawer(GravityCompat.START)
            when (menuItem.itemId) {
                R.id.nav_dashboard -> { }
                R.id.nav_approve_class -> startActivity(Intent(this, PendingClassesActivity::class.java))
                R.id.nav_deletion_requests -> startActivity(Intent(this, DeletionRequestsActivity::class.java))
                R.id.nav_share_config -> startActivity(Intent(this, ShareConfigActivity::class.java))
                R.id.nav_pending -> startActivity(Intent(this, PendingTeachersActivity::class.java))
                R.id.nav_attendance -> startActivity(Intent(this, AttendanceActivity::class.java))
                R.id.nav_report -> startActivity(Intent(this, ReportActivity::class.java))
                R.id.nav_chart -> startActivity(Intent(this, ChartActivity::class.java))
                R.id.nav_sms -> startActivity(Intent(this, SmsActivity::class.java))
                R.id.nav_settings -> startActivity(Intent(this, SettingsActivity::class.java))
                // FIX(admin-notifications): ورودیِ گمشده‌ی «مرکز اعلان‌ها» — قبلاً هیچ‌جای اپ این
                // صفحه را باز نمی‌کرد (فقط در AndroidManifest ثبت بود) ⇒ اعلان ادمین هرگز دیده نمی‌شد.
                R.id.nav_notifications -> startActivity(Intent(this, NotificationCenterActivity::class.java))
                R.id.nav_institute_settings -> startActivity(Intent(this, InstituteSettingsActivity::class.java))
                R.id.nav_deleted_classes -> openArchivedClasses()
                R.id.nav_audit_radar -> {
                    if (dashboardSubRole != "admin") {
                        Toast.makeText(this, getString(R.string.common_no_access), Toast.LENGTH_SHORT).show()
                    } else {
                        startActivity(Intent(this, AuditDashboardActivity::class.java))
                    }
                }
                R.id.nav_dunning -> {
                    if (dashboardSubRole != "admin") {
                        Toast.makeText(this, getString(R.string.common_no_access), Toast.LENGTH_SHORT).show()
                    } else {
                        startActivity(Intent(this, DunningActivity::class.java))
                    }
                }
                R.id.nav_admin_dashboard -> {
                    if (dashboardSubRole != "admin") {
                        Toast.makeText(this, getString(R.string.common_no_access), Toast.LENGTH_SHORT).show()
                    } else {
                        startActivity(Intent(this, AdminDashboardActivity::class.java))
                    }
                }
                R.id.nav_havale -> {
                    val intent = Intent(this, InvoiceActivity::class.java).apply { putExtra("IS_ADMIN", true) }
                    startActivity(intent)
                }
                R.id.nav_classes -> startActivity(Intent(this, ClassManagementActivity::class.java))
                R.id.nav_parents -> startActivity(Intent(this, ParentContactsActivity::class.java))
                R.id.nav_register -> showRegisterDialog()
            }
            true
        }
    }

    private fun setupMenuClickListeners(subRole: String) {
        // Audit Radar grid card: admin-only visibility
        findViewById<View>(R.id.menu_14_audit)?.let { auditCard ->
            auditCard.visibility = if (subRole == "admin") View.VISIBLE else View.GONE
        }
        findViewById<View>(R.id.menu_15_dunning)?.let { dunningCard ->
            dunningCard.visibility = if (subRole == "admin") View.VISIBLE else View.GONE
        }
        findViewById<View>(R.id.menu_16_dashboard)?.let { dashboardCard ->
            dashboardCard.visibility = if (subRole == "admin") View.VISIBLE else View.GONE
        }
        // ۱. پیشخوان
        findViewById<View>(R.id.menu_1_dashboard).setOnClickListener {
            Toast.makeText(this, getString(R.string.main_already_home), Toast.LENGTH_SHORT).show()
        }

        // ۲. ثبت‌نام سریع
        findViewById<View>(R.id.menu_2_register).setOnClickListener {
            showRegisterDialog()
        }

        // ۳. لیست دانش‌آموزان
        findViewById<View>(R.id.menu_3_students).setOnClickListener {
            val intent = Intent(this, PersonListActivity::class.java).apply { putExtra("MODE", "STUDENT") }
            startActivity(intent)
        }

        // ۴. لیست معلمان
        findViewById<View>(R.id.menu_4_teachers).setOnClickListener {
            val intent = Intent(this, PersonListActivity::class.java).apply { putExtra("MODE", "TEACHER") }
            startActivity(intent)
        }

        // ۵. مدیریت (باز شدن منوی کشویی آکاردئونی)
        findViewById<View>(R.id.menu_5_management).setOnClickListener {
            showManagementAccordionDialog(subRole)
        }

        // ۶. گزارش‌گیری
        findViewById<View>(R.id.menu_6_reports).setOnClickListener {
            if (subRole == "secretary") {
                Toast.makeText(this, getString(R.string.common_no_access), Toast.LENGTH_SHORT).show()
            } else {
                startActivity(Intent(this, ReportActivity::class.java))
            }
        }

        // ۷. پیامک
        findViewById<View>(R.id.menu_7_sms).setOnClickListener {
            startActivity(Intent(this, SmsActivity::class.java))
        }

        // ۸. تنظیمات مرکزی
        findViewById<View>(R.id.menu_8_settings).setOnClickListener {
            if (subRole == "secretary") {
                Toast.makeText(this, getString(R.string.common_no_access), Toast.LENGTH_SHORT).show()
            } else {
                startActivity(Intent(this, InstituteSettingsActivity::class.java))
            }
        }

        // ۹. ثبت حواله سریع
        findViewById<View>(R.id.menu_9_quick_invoice).setOnClickListener {
            val intent = Intent(this, InvoiceActivity::class.java).apply { putExtra("IS_ADMIN", true) }
            startActivity(intent)
        }

        // ۱۰. صدور صورت‌حساب
        findViewById<View>(R.id.menu_10_statement).setOnClickListener {
            startActivity(Intent(this, ReportActivity::class.java))
        }

        // ۱۱. نمرات کلاسی
        findViewById<View>(R.id.menu_11_grades).setOnClickListener {
            startActivity(Intent(this, SubmitGradeActivity::class.java))
        }

        // ۱۲. اصلاح حضور غیاب
        findViewById<View>(R.id.menu_12_sessions).setOnClickListener {
            showEditSessionDialog()
        }

        // ۱۳. کلاس‌های در حال برگزاری (زنده)
        findViewById<View>(R.id.menu_13_live).setOnClickListener {
            startActivity(Intent(this, LiveClassesActivity::class.java))
        }

        // ۱۴. رادار تقلب (Audit Radar) — فقط ادمین
        findViewById<View>(R.id.menu_14_audit)?.setOnClickListener {
            if (subRole != "admin") {
                Toast.makeText(this, getString(R.string.common_no_access), Toast.LENGTH_SHORT).show()
            } else {
                startActivity(Intent(this, AuditDashboardActivity::class.java))
            }
        }
        // ۱۵. یادآوری اقساط (Dunning) — فقط ادمین
        findViewById<View>(R.id.menu_15_dunning)?.setOnClickListener {
            if (subRole != "admin") {
                Toast.makeText(this, getString(R.string.common_no_access), Toast.LENGTH_SHORT).show()
            } else {
                startActivity(Intent(this, DunningActivity::class.java))
            }
        }
        // ۱۶. داشبورد مدیریت (Command Center) — فقط ادمین
        findViewById<View>(R.id.menu_16_dashboard)?.setOnClickListener {
            if (subRole != "admin") {
                Toast.makeText(this, getString(R.string.common_no_access), Toast.LENGTH_SHORT).show()
            } else {
                startActivity(Intent(this, AdminDashboardActivity::class.java))
            }
        }
    }

    // 🆕 دریافت تعداد کلاس‌های زنده برای نشانگر قرمز پیشخوان (ادمین/منشی)
    private fun fetchLiveSessionCount() {
        val api = RetrofitClient.getInstance(this).create(LiveApi::class.java)
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val list = api.getLiveSessions()
                withContext(Dispatchers.Main) {
                    val count = list.size
                    val tvLiveCount = findViewById<TextView>(R.id.txtLiveCount)
                    val imgPulse = findViewById<ImageView>(R.id.imgLivePulse)
                    if (count > 0) {
                        tvLiveCount.text = getString(R.string.main_live_count, count)
                        imgPulse.imageTintList = android.content.res.ColorStateList.valueOf(UiColors.resolve(this@MainActivity, R.color.status_danger))
                    } else {
                        tvLiveCount.text = getString(R.string.main_live)
                        imgPulse.imageTintList = android.content.res.ColorStateList.valueOf(UiColors.resolve(this@MainActivity, R.color.text_disabled))
                    }
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                // اگر خطای شبکه بود، نشانگر بدون تعداد باقی می‌ماند
            }
        }
    }

    private fun fetchTodaySummary(forceRefresh: Boolean = false) {
        if (todaySummaryLoading) return
        todaySummaryLoading = true

        val api = RetrofitClient.getInstance(this).create(TodaySummaryApi::class.java)
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val summary = TodaySummaryShortCache.getOrFetch(
                    context = this@MainActivity,
                    key = "today_summary_admin_$dashboardSubRole",
                    modelClass = AdminTodaySummary::class.java,
                    forceRefresh = forceRefresh
                ) {
                    api.getAdminTodaySummary()
                }
                withContext(Dispatchers.Main) {
                    renderTodaySummary(summary)
                }
            } catch (ignoredError: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (ignoredError is kotlinx.coroutines.CancellationException) throw ignoredError;
                // داده لحظه‌ای است؛ کش منقضی‌شده عمداً نمایش داده نمی‌شود.
            } finally {
                withContext(Dispatchers.Main) {
                    todaySummaryLoading = false
                }
            }
        }
    }

    private fun renderTodaySummary(summary: AdminTodaySummary) {
        findViewById<TextView>(R.id.tvTodayClassesValue).text = summary.scheduledClasses.toString()
        findViewById<TextView>(R.id.tvTodayClassesSub).text = getString(R.string.main_started, summary.startedClasses)
        findViewById<TextView>(R.id.tvTodayEnrollmentsValue).text = summary.todayEnrollments.toString()

        val paymentValue = findViewById<TextView>(R.id.tvTodayPaymentsValue)
        paymentValue.text = if (summary.paymentVisible && summary.todayPayments != null) {
            String.format(java.util.Locale.US, "%,d", summary.todayPayments)
        } else {
            getString(R.string.common_restricted)
        }

        currentLateClasses = summary.lateClasses
        val lateContainer = findViewById<View>(R.id.layoutLateClassAlert)
        val lateText = findViewById<TextView>(R.id.tvLateClassAlert)
        if (currentLateClasses.isEmpty()) {
            lateContainer.visibility = View.GONE
            lateContainer.setOnClickListener(null)
        } else {
            lateContainer.visibility = View.VISIBLE
            val visibleAlerts = currentLateClasses.take(2).joinToString("\n") { item ->
                getString(R.string.main_late_row, item.className, item.teacherName, item.minutesLate)
            }
            val remaining = currentLateClasses.size - 2
            lateText.text = if (remaining > 0) {
                getString(R.string.main_more_alerts, visibleAlerts, remaining)
            } else {
                visibleAlerts
            }
            lateContainer.setOnClickListener { showLateClassDetails() }
        }

        renderSmartFinancialAlerts(summary)
    }

    private fun renderSmartFinancialAlerts(summary: AdminTodaySummary) {
        val section = findViewById<View>(R.id.layoutSmartFinancialAlerts)
        val installmentRow = findViewById<View>(R.id.layoutInstallmentAlerts)
        val teacherRow = findViewById<View>(R.id.layoutTeacherSettlementAlerts)

        if (!summary.smartAlertsVisible || dashboardSubRole != "admin") {
            currentInstallmentAlerts = emptyList()
            currentTeacherSettlementAlerts = emptyList()
            section.visibility = View.GONE
            return
        }

        val installmentGroup = summary.installmentAlerts
        val teacherGroup = summary.teacherSettlementAlerts
        currentInstallmentAlerts = installmentGroup?.items.orEmpty()
        currentTeacherSettlementAlerts = teacherGroup?.items.orEmpty()

        installmentRow.visibility = if (currentInstallmentAlerts.isEmpty()) View.GONE else View.VISIBLE
        teacherRow.visibility = if (currentTeacherSettlementAlerts.isEmpty()) View.GONE else View.VISIBLE
        section.visibility = if (
            currentInstallmentAlerts.isEmpty() && currentTeacherSettlementAlerts.isEmpty()
        ) View.GONE else View.VISIBLE

        if (currentInstallmentAlerts.isNotEmpty() && installmentGroup != null) {
            val oldest = currentInstallmentAlerts.first()
            val delay = if (oldest.daysOverdue == 0) {
                getString(R.string.main_due_today)
            } else {
                getString(R.string.main_days_overdue, oldest.daysOverdue)
            }
            findViewById<TextView>(R.id.tvInstallmentAlertSummary).text =
                getString(R.string.main_inst_group, installmentGroup.count, formatMoney(installmentGroup.totalAmount)) +
                    getString(R.string.main_oldest_student, oldest.studentName, delay)
            findViewById<View>(R.id.btnInstallmentAlerts).setOnClickListener {
                showInstallmentAlerts()
            }
        }

        if (currentTeacherSettlementAlerts.isNotEmpty() && teacherGroup != null) {
            val threshold = summary.teacherSettlementAlertDays ?: 30
            val oldest = currentTeacherSettlementAlerts.first()
            findViewById<TextView>(R.id.tvTeacherSettlementAlertSummary).text =
                getString(R.string.main_teacher_group, teacherGroup.count, formatMoney(teacherGroup.totalAmount)) +
                    getString(R.string.main_oldest_teacher, oldest.teacherName, oldest.oldestDaysUnsettled, threshold)
            findViewById<View>(R.id.btnTeacherSettlementAlerts).setOnClickListener {
                showTeacherSettlementAlerts()
            }
        }
    }

    private fun formatMoney(amount: Long): String =
        String.format(java.util.Locale.US, "%,d", amount)

    private fun showInstallmentAlerts() {
        if (currentInstallmentAlerts.isEmpty()) return

        val labels = currentInstallmentAlerts.map { item ->
            val delay = if (item.daysOverdue == 0) getString(R.string.main_due_today) else getString(R.string.main_days_overdue, item.daysOverdue)
            getString(R.string.main_inst_row, item.studentName, formatMoney(item.amount), delay)
        }.toTypedArray()
        AlertDialog.Builder(this)
            .setTitle(getString(R.string.main_title_overdue_inst))
            .setItems(labels) { _, which -> openStudentInstallments(currentInstallmentAlerts[which]) }
            .setNegativeButton(getString(R.string.btn_dismiss), null)
            .show()
    }

    private fun openStudentInstallments(item: DueInstallmentAlert) {
        startActivity(Intent(this, StudentProfileActivity::class.java).apply {
            putExtra("STUDENT_ID", item.studentId)
            putExtra("OPEN_INSTALLMENTS_TAB", true)
        })
    }

    private fun showTeacherSettlementAlerts() {
        if (currentTeacherSettlementAlerts.isEmpty()) return

        val labels = currentTeacherSettlementAlerts.map { item ->
            getString(R.string.main_teacher_row, item.teacherName, formatMoney(item.unsettledAmount), item.oldestDaysUnsettled)
        }.toTypedArray()
        AlertDialog.Builder(this)
            .setTitle(getString(R.string.main_title_teacher_settle))
            .setItems(labels) { _, which ->
                openTeacherSettlement(currentTeacherSettlementAlerts[which])
            }
            .setNegativeButton(getString(R.string.btn_dismiss), null)
            .show()
    }

    private fun openTeacherSettlement(item: TeacherSettlementAlert) {
        startActivity(Intent(this, TeacherProfileActivity::class.java).apply {
            putExtra("TEACHER_ID", item.teacherId)
            putExtra("OPEN_SETTLEMENT_TAB", true)
        })
    }

    private fun showLateClassDetails() {
        if (currentLateClasses.isEmpty()) return
        if (currentLateClasses.size == 1) {
            openClassDetails(currentLateClasses.first())
            return
        }

        val labels = currentLateClasses.map { item ->
            getString(R.string.main_late_class_row, item.className, item.teacherName, item.minutesLate)
        }.toTypedArray()
        AlertDialog.Builder(this)
            .setTitle(getString(R.string.main_title_late))
            .setItems(labels) { _, which -> openClassDetails(currentLateClasses[which]) }
            .setNegativeButton(getString(R.string.btn_dismiss), null)
            .show()
    }

    private fun openClassDetails(item: LateClassAlert) {
        val intent = Intent(this, ClassDetailActivity::class.java).apply {
            putExtra("CLASS_ID", item.courseId)
            putExtra("CLASS_NAME", item.className)
        }
        startActivity(intent)
    }

    override fun onResume() {
        super.onResume()
        fetchLiveSessionCount()
        fetchTodaySummary()
    }

    private fun showManagementAccordionDialog(subRole: String) {
        val options = if (subRole == "secretary") {
            arrayOf(getString(R.string.main_menu_active_classes), getString(R.string.main_menu_special_class))
        } else {
            arrayOf(
                getString(R.string.main_menu_txn),
                getString(R.string.main_menu_share),
                getString(R.string.main_menu_teachers),
                getString(R.string.main_menu_active),
                getString(R.string.main_menu_pending),
                getString(R.string.main_menu_trash),
                getString(R.string.main_menu_crm),
                getString(R.string.main_menu_audit_radar),
                getString(R.string.main_menu_dunning),
                getString(R.string.main_menu_dashboard)
            )
        }

        AlertDialog.Builder(this)
            .setTitle(getString(R.string.main_menu_title))
            .setItems(options) { _, which ->
                if (subRole == "secretary") {
                    when (which) {
                        0 -> startActivity(Intent(this, ClassManagementActivity::class.java))
                        1 -> startActivity(Intent(this, AddClassActivity::class.java).apply { putExtra("IS_ADMIN_MODE", true) })
                    }
                } else {
                    when (which) {
                        0 -> startActivity(Intent(this, TransactionManageActivity::class.java))
                        1 -> startActivity(Intent(this, ShareConfigActivity::class.java))
                        2 -> startActivity(Intent(this, PendingTeachersActivity::class.java))
                        3 -> startActivity(Intent(this, ClassManagementActivity::class.java))
                        4 -> startActivity(Intent(this, PendingClassesActivity::class.java))
                        5 -> openArchivedClasses()
                        6 -> startActivity(Intent(this, CrmLeadsActivity::class.java))
                        7 -> startActivity(Intent(this, AuditDashboardActivity::class.java))
                        8 -> startActivity(Intent(this, DunningActivity::class.java))
                        9 -> startActivity(Intent(this, AdminDashboardActivity::class.java))
                    }
                }
            }
            .show()
    }

    private fun fetchInstituteSettingsName() {
        val retrofit = RetrofitClient.getInstance(this)
        val api = retrofit.create(DashboardSettingsApi::class.java)

        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.

        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val settings = api.getSettings()
                withContext(Dispatchers.Main) {
                    tvHeaderMainTitle.text = settings.name
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                // خطای شبکه نادیده گرفته می‌شود و نام پیش‌فرض نمایش می‌یابد
            }
        }
    }

    private fun showRegisterDialog() {
        val options = arrayOf(getString(R.string.main_reg_student), getString(R.string.main_reg_teacher))
        AlertDialog.Builder(this)
            .setTitle(getString(R.string.main_reg_title))
            .setItems(options) { _, which ->
                when (which) {
                    0 -> startActivity(Intent(this, StudentRegisterActivity::class.java))
                    1 -> startActivity(Intent(this, TeacherRegisterActivity::class.java))
                }
            }
            .show()
    }

    /**
     * «کلاس‌های حذفی (آرشیو ادمین)» — قبلاً یک AlertDialog خشک بود؛ حالا صفحهٔ مستقل با جست‌وجو
     * (نام کلاس/معلم/کد/بازهٔ تاریخ حذف) و صفحهٔ گزارش کامل هر کلاس (ArchivedClassDetailActivity).
     */
    private fun openArchivedClasses() {
        startActivity(Intent(this, ArchivedClassesActivity::class.java))
    }

    private fun showEditSessionDialog() {
        val view = LayoutInflater.from(this).inflate(R.layout.dialog_ip_input, null)
        val etInput = view.findViewById<android.widget.EditText>(R.id.etIpInput)
        etInput.hint = getString(R.string.main_session_code_hint)
        etInput.inputType = android.text.InputType.TYPE_CLASS_NUMBER

        AlertDialog.Builder(this)
            .setTitle(getString(R.string.main_edit_session_title))
            .setView(view)
            .setPositiveButton(getString(R.string.main_edit_session_go)) { _, _ ->
                val codeStr = etInput.text.toString().trim()
                val code = codeStr.toIntOrNull()
                if (code != null) {
                    val intent = Intent(this, AttendanceActivity::class.java).apply {
                        putExtra("MODE", "EDIT_SESSION")
                        putExtra("TARGET_SESSION_CODE", code)
                    }
                    startActivity(intent)
                } else {
                    Toast.makeText(this, getString(R.string.main_session_invalid), Toast.LENGTH_SHORT).show()
                }
            }
            .setNegativeButton(getString(R.string.common_cancel), null)
            .show()
    }

    private fun animateEntrance() {
        val menuIds = intArrayOf(
            R.id.menu_1_dashboard, R.id.menu_2_register, R.id.menu_3_students, R.id.menu_4_teachers,
            R.id.menu_5_management, R.id.menu_6_reports, R.id.menu_7_sms, R.id.menu_8_settings,
            R.id.menu_9_quick_invoice, R.id.menu_10_statement, R.id.menu_11_grades, R.id.menu_12_sessions,
            R.id.menu_13_live, R.id.menu_14_audit, R.id.menu_15_dunning, R.id.menu_16_dashboard
        )
        menuIds.forEachIndexed { index, id ->
            val view = findViewById<View>(id) ?: return@forEachIndexed
            view.alpha = 0f
            view.translationY = 100f
            view.animate()
                .alpha(1f)
                .translationY(0f)
                .setStartDelay(index * 60L)
                .setDuration(400)
                .setInterpolator(DecelerateInterpolator())
                .start()
        }
    }

    private fun getCurrentShamsiDate(): String {
        val calendar = java.util.Calendar.getInstance()
        val gy = calendar.get(java.util.Calendar.YEAR)
        val gm = calendar.get(java.util.Calendar.MONTH) + 1
        val gd = calendar.get(java.util.Calendar.DAY_OF_MONTH)

        var jy = gy - 621
        if (gm < 3 || (gm == 3 && gd < 21)) {
            jy = gy - 622
        }
        val jm = when (gm) {
            1 -> 10
            2 -> 11
            3 -> if (gd < 21) 12 else 1
            4 -> if (gd < 21) 1 else 2
            5 -> if (gd < 21) 2 else 3
            6 -> if (gd < 21) 3 else 4
            7 -> if (gd < 21) 4 else 5
            8 -> if (gd < 21) 5 else 6
            9 -> if (gd < 21) 6 else 7
            10 -> if (gd < 21) 7 else 8
            11 -> if (gd < 21) 8 else 9
            12 -> if (gd < 21) 9 else 10
            else -> 1
        }
        
        val dayOfWeek = when (calendar.get(java.util.Calendar.DAY_OF_WEEK)) {
            java.util.Calendar.SATURDAY -> getString(R.string.day_saturday)
            java.util.Calendar.SUNDAY -> getString(R.string.day_sunday)
            java.util.Calendar.MONDAY -> getString(R.string.day_monday)
            java.util.Calendar.TUESDAY -> getString(R.string.day_tuesday)
            java.util.Calendar.WEDNESDAY -> getString(R.string.day_wednesday)
            java.util.Calendar.THURSDAY -> getString(R.string.day_thursday)
            java.util.Calendar.FRIDAY -> getString(R.string.day_friday)
            else -> getString(R.string.common_today)
        }

        val monthName = when (jm) {
            1 -> getString(R.string.month_farvardin)
            2 -> getString(R.string.month_ordibehesht)
            3 -> getString(R.string.month_khordad)
            4 -> getString(R.string.month_tir)
            5 -> getString(R.string.month_mordad)
            6 -> getString(R.string.month_shahrivar)
            7 -> getString(R.string.month_mehr)
            8 -> getString(R.string.month_aban)
            9 -> getString(R.string.month_azar)
            10 -> getString(R.string.month_dey)
            11 -> getString(R.string.month_bahman)
            12 -> getString(R.string.month_esfand)
            else -> ""
        }

        val jd = when (gm) {
            1 -> if (gd < 21) gd + 11 else gd - 20
            2 -> if (gd < 20) gd + 11 else gd - 19
            3 -> if (gd < 21) gd + 9 else gd - 20
            4 -> if (gd < 21) gd + 10 else gd - 20
            5 -> if (gd < 22) gd + 11 else gd - 21
            6 -> if (gd < 22) gd + 10 else gd - 21
            7 -> if (gd < 23) gd + 9 else gd - 22
            8 -> if (gd < 23) gd + 9 else gd - 22
            9 -> if (gd < 23) gd + 9 else gd - 22
            10 -> if (gd < 23) gd + 8 else gd - 22
            11 -> if (gd < 22) gd + 9 else gd - 21
            12 -> if (gd < 21) gd + 9 else gd - 20
            else -> gd
        }

        return getString(R.string.main_date_format, dayOfWeek, jd, monthName, jy)
    }

    override fun onDestroy() {
        super.onDestroy()
        handler.removeCallbacks(clockRunnable)
    }

    private fun fetchPermissionsAndSyncUI() {
        val retrofit = RetrofitClient.getInstance(this)
        val api = retrofit.create(MeApi::class.java)
        
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val me = api.getMe()
                val prefs = getSharedPreferences("UserCreds", Context.MODE_PRIVATE)
                prefs.edit().putStringSet("USER_PERMISSIONS", me.permissions.toSet()).apply()
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                android.util.Log.e("MainActivity", "fetchPermissionsAndSyncUI failed", e)
            }
        }
    }
}
