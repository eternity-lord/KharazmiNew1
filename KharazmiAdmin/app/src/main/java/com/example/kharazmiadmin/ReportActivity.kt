package com.example.kharazmiadmin

import android.app.AlertDialog
import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.print.PrintAttributes
import android.print.PrintManager
import android.view.View
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.*
import androidx.lifecycle.lifecycleScope
import com.google.android.material.textfield.TextInputEditText
import com.google.android.material.textfield.TextInputLayout
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.ResponseBody
import retrofit2.Response
import retrofit2.http.GET
import retrofit2.http.Query
import retrofit2.http.Streaming

// مدل‌های داده برای رتروفیت جدید گزارش‌گیری متمرکز
data class FinancialSummaryResponse(
    val user_type: String,
    val year: Int,
    val month: Int,
    val monthly: FinancialMetrics,
    val yearly: FinancialMetrics,
    // O-10: پرداخت‌های بی‌تاریخ در جمع‌های ماه/سال نمی‌آیند؛ این دو فیلد آن‌ها را آشکار می‌کنند.
    // nullable با پیش‌فرض تا اپ با پاسخ سرورِ قدیمی هم نشکند.
    val undated_count: Int? = null,
    val undated_amount: Long? = null,
    // توضیح «چرا صفر است؟» — nullable تا سرور قدیمی اپ را نشکند
    val diagnostics: ReportDiagnostics? = null
)

data class ReportDiagnostics(
    val session_charges_total: Int = 0,
    val session_charges_in_period: Int = 0,
    val session_charges_undated: Int = 0,
    val last_session_charge_date: String? = null,
    val prepaid_count: Int = 0,
    val prepaid_amount: Long = 0
)

data class FinancialMetrics(
    val total: Long,
    val collected: Long,
    val uncollected: Long
)

data class PaymentTimelineItem(
    val transaction_id: Int? = null, val date: String? = null,
    val amount: Long? = null, val target_wallet: String? = null,
    val payment_link: String? = null
)

data class NextInstallmentItem(
    val id: Int? = null, val amount: Long? = null, val due_date: String? = null,
    val remaining_amount: Long? = null, val payment_link: String? = null
)

data class StudentStatementTeacher(
    val enrollment_id: Int? = null,
    val teacher_id: Int? = null,
    val teacher_name: String? = null,
    val course_id: Int? = null,
    val course_title: String? = null,
    val course_code: String? = null,
    val branch_id: Int? = null,
    val paid_teacher: Long = 0,
    val paid_institute: Long = 0,
    val debt_teacher: Long = 0,
    val debt_institute: Long = 0,
    val debt: Long = 0,
    val tuition: Long = 0,
    val enrollment_status: String? = null,
    val teacher_profile_path: String? = null,
    val is_unassigned: Boolean = false
)

data class StudentStatementResponse(
    val student_id: Int,
    val student_name: String,
    val student_code: String,
    val total_paid_institute: Long,
    val total_debt_institute: Long,
    // Class-scoped totals are separate from the legacy aggregate wallet fields.
    val class_paid_institute: Long? = null,
    val class_debt_institute: Long? = null,
    val class_debt_total: Long? = null,
    val unassigned_debt: Long = 0,
    val teacher_name: String? = null,
    val teachers: List<StudentStatementTeacher> = emptyList(),
    val payment_timeline: List<PaymentTimelineItem> = emptyList(),
    val next_installment: NextInstallmentItem? = null,
    val payment_link: String? = null,
    val institute_card_number: String,
    val institute_name: String,
    val address: String,
    val phone: String,
    val footer_text: String
)

data class SearchStudentItem(
    val type: String,
    val id: Int,
    val title: String,
    val subtitle: String,
    val info: String,
    val student_id: Int? = null
)

data class TeacherItem(
    val id: Int,
    // FIX(null-data): نام legacy ممکن است null باشد — null‌پذیر تا فیلتر گزارش (لیست مربیان)
    // با یک رکورد ناقص نشکند؛ فال‌بک در محل نمایش.
    val first_name: String? = null,
    val last_name: String? = null
)

interface ReportNewApi {
    @GET("teachers/list")
    suspend fun getTeachersList(): List<TeacherItem>

    @Streaming
    @GET("reports/financial/excel")
    suspend fun exportFinancial(
        @Query("start_date") startDate: String?,
        @Query("end_date") endDate: String?,
        @Query("branch_id") branchId: Int? = null,
        @Query("teacher_id") teacherId: Int? = null
    ): Response<ResponseBody>

    @GET("reports/financial_summary")
    suspend fun getFinancialSummary(
        @Query("user_type") userType: String,
        @Query("teacher_id") teacherId: Int?,
        @Query("year") year: Int?,
        @Query("month") month: Int?
    ): FinancialSummaryResponse

    @GET("finance/search_advanced")
    suspend fun searchAdvanced(
        @Query("query") query: String
    ): List<SearchStudentItem>

    @GET("reports/student_statement")
    suspend fun getStudentStatement(
        @Query("student_id") studentId: Int
    ): StudentStatementResponse
}

class ReportActivity : BaseActivity() {

    private lateinit var api: ReportNewApi
    
    // فیلترها و کامپوننت‌های محدوده
    private lateinit var rgReportScope: RadioGroup
    private lateinit var rbScopeInstitute: RadioButton
    private lateinit var rbScopeTeacher: RadioButton
    private lateinit var tilTeacherFilter: TextInputLayout
    private lateinit var acTeacherFilter: AutoCompleteTextView
    private lateinit var acYearFilter: AutoCompleteTextView
    private lateinit var acMonthFilter: AutoCompleteTextView
    private lateinit var btnFetchFinancialSummary: Button
    private lateinit var btnExportFinancial: Button
    // O-10: خط هشدار پول بی‌تاریخ (nullable: اگر چیدمان قدیمی بود، اپ نباید بشکند)
    private var tvUndatedWarning: TextView? = null
    private var tvReportStatus: TextView? = null
    private var tvReportHint: TextView? = null

    // مقادیر خروجی آمار مالی
    private lateinit var tvMonthlyTitle: TextView
    private lateinit var tvMonthlyTotal: TextView
    private lateinit var tvMonthlyCollected: TextView
    private lateinit var tvMonthlyUncollected: TextView
    
    private lateinit var cardYearlySummary: View
    private lateinit var tvYearlyTitle: TextView
    private lateinit var tvYearlyTotal: TextView
    private lateinit var tvYearlyCollected: TextView
    private lateinit var tvYearlyUncollected: TextView

    // بخش صورت‌حساب دانش‌آموز
    private lateinit var etStudentSearchName: TextInputEditText
    private lateinit var btnSearchStudentStatement: Button
    private lateinit var llStatementResult: View
    private lateinit var tvStatementStudentName: TextView
    private lateinit var tvStatementStudentCode: TextView
    private lateinit var tvStatementPaid: TextView
    private lateinit var tvStatementDebt: TextView
    private lateinit var tvStatementTeacher: TextView
    private lateinit var tvStatementNextDue: TextView
    private lateinit var tvStatementTimeline: TextView
    private lateinit var btnStatementPay: Button
    private lateinit var btnPrintStatement: Button

    // حالت‌ها و متغیرهای کمکی
    private var teachersList: List<TeacherItem> = emptyList()
    private var selectedTeacherId: Int? = null
    private var currentUserRole: String = ""
    private var currentStudentIdForPrint: Int? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_report)

        // ۱. انتساب ویوها
        rgReportScope = findViewById(R.id.rgReportScope)
        rbScopeInstitute = findViewById(R.id.rbScopeInstitute)
        rbScopeTeacher = findViewById(R.id.rbScopeTeacher)
        tilTeacherFilter = findViewById(R.id.tilTeacherFilter)
        acTeacherFilter = findViewById(R.id.acTeacherFilter)
        acYearFilter = findViewById(R.id.acYearFilter)
        acMonthFilter = findViewById(R.id.acMonthFilter)
        btnFetchFinancialSummary = findViewById(R.id.btnFetchFinancialSummary)
        btnExportFinancial = findViewById(R.id.btnExportFinancial)
        tvUndatedWarning = findViewById(R.id.tvUndatedWarning)
        tvReportStatus = findViewById(R.id.tvReportStatus)
        tvReportHint = findViewById(R.id.tvReportHint)

        tvMonthlyTitle = findViewById(R.id.tvMonthlyTitle)
        tvMonthlyTotal = findViewById(R.id.tvMonthlyTotal)
        tvMonthlyCollected = findViewById(R.id.tvMonthlyCollected)
        tvMonthlyUncollected = findViewById(R.id.tvMonthlyUncollected)

        cardYearlySummary = findViewById(R.id.cardYearlySummary)
        tvYearlyTitle = findViewById(R.id.tvYearlyTitle)
        tvYearlyTotal = findViewById(R.id.tvYearlyTotal)
        tvYearlyCollected = findViewById(R.id.tvYearlyCollected)
        tvYearlyUncollected = findViewById(R.id.tvYearlyUncollected)

        etStudentSearchName = findViewById(R.id.etStudentSearchName)
        btnSearchStudentStatement = findViewById(R.id.btnSearchStudentStatement)
        llStatementResult = findViewById(R.id.llStatementResult)
        tvStatementStudentName = findViewById(R.id.tvStatementStudentName)
        tvStatementStudentCode = findViewById(R.id.tvStatementStudentCode)
        tvStatementPaid = findViewById(R.id.tvStatementPaid)
        tvStatementDebt = findViewById(R.id.tvStatementDebt)
        tvStatementTeacher = findViewById(R.id.tvStatementTeacher)
        tvStatementNextDue = findViewById(R.id.tvStatementNextDue)
        tvStatementTimeline = findViewById(R.id.rvPaymentTimeline)
        btnStatementPay = findViewById(R.id.btnStatementPay)
        btnPrintStatement = findViewById(R.id.btnPrintStatement)
        
        ButtonAnimator.applyPillScaleAnimation(btnFetchFinancialSummary)
        ButtonAnimator.applyPillScaleAnimation(btnSearchStudentStatement)
        ButtonAnimator.applyPillScaleAnimation(btnPrintStatement)

        // ۲. دریافت اطلاعات ورود و امنیت مربی
        val credsPrefs = getSharedPreferences("UserCreds", Context.MODE_PRIVATE)
        currentUserRole = credsPrefs.getString("USER_ROLE", "") ?: ""

        val retrofit = RetrofitClient.getInstance(this)
        api = retrofit.create(ReportNewApi::class.java)

        // ۳. پر کردن گزینه‌های سال و ماه شمسی
        setupDateDropdowns()

        // ۴. بررسی دسترسی‌ها
        if (currentUserRole == "teacher") {
            // مخفی‌سازی کامل بخش انتخاب آموزشگاه/معلم برای مربی لاگین شده
            findViewById<View>(R.id.cardReportTypeSelector).visibility = View.GONE
            tilTeacherFilter.visibility = View.GONE
            rbScopeTeacher.isChecked = true
            // لود اطلاعات خودش به صورت مستقیم
            fetchReport("teacher")
        } else {
            // مدیر یا منشی
            fetchTeachersList()
            rgReportScope.setOnCheckedChangeListener { _, checkedId ->
                if (checkedId == R.id.rbScopeTeacher) {
                    tilTeacherFilter.visibility = View.VISIBLE
                    cardYearlySummary.visibility = View.VISIBLE
                } else {
                    tilTeacherFilter.visibility = View.GONE
                    cardYearlySummary.visibility = View.GONE
                }
            }
        }

        // ۵. دکمه دریافت گزارش آمار مالی
        btnFetchFinancialSummary.setOnClickListener {
            val scope = if (rbScopeTeacher.isChecked) "teacher" else "institute"
            fetchReport(scope)
        }
        btnExportFinancial.setOnClickListener { exportFinancialReport() }

        // ۶. دکمه جستجوی صورت‌حساب دانش‌آموز
        btnSearchStudentStatement.setOnClickListener {
            performStudentSearch()
        }

        // ۷. دکمه پرینت و چاپ رسمی صورت‌حساب
        btnPrintStatement.setOnClickListener {
            currentStudentIdForPrint?.let { studentId ->
                printStatementDirect(studentId)
            } ?: Toast.makeText(this, getString(R.string.rpt_no_student), Toast.LENGTH_SHORT).show()
        }
        // دکمهٔ پرداخت فقط پس از دریافت صورت‌حساب و با شناسهٔ واقعی دانش‌آموز فعال می‌شود.
        btnStatementPay.visibility = View.GONE
    }

    private fun setupDateDropdowns() {
        // سال‌های شمسی انتخابی
        val years = arrayOf("1404", "1405", "1406", "1407")
        val yearAdapter = ArrayAdapter(this, android.R.layout.simple_dropdown_item_1line, years)
        acYearFilter.setAdapter(yearAdapter)

        // ماه‌های شمسی انتخابی
        val months = arrayOf("01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12")
        val monthAdapter = ArrayAdapter(this, android.R.layout.simple_dropdown_item_1line, months)
        acMonthFilter.setAdapter(monthAdapter)

        // سال و ماه جاری شمسی با مبدل دقیق پروژه (قبلاً تقریب «روز ۲۱ هر ماه» بود که در چند ماه
        // ۱–۲ روز آخر/اول ماه را به ماه قبل/بعد می‌برد و گزارش ماه اشتباه را نشان می‌داد).
        val today = JalaliUtils.todayJalaliString().split("/")
        val jy = today[0].toInt()
        val jm = today[1].toInt()

        acYearFilter.setText(jy.toString(), false)
        acMonthFilter.setText(String.format(java.util.Locale.US, "%02d", jm), false)
    }

    private fun fetchTeachersList() {
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val list = api.getTeachersList()
                teachersList = list
                withContext(Dispatchers.Main) {
                    // FIX(null-data): نام ناقص/خالی نباید «null» یا ردیف خالی در فیلتر معلم بدهد.
                    val fallbackName = getString(R.string.common_person_unknown)
                    val teacherNames = list.map {
                        "${it.first_name ?: ""} ${it.last_name ?: ""}".trim().ifEmpty { fallbackName } + " (${it.id})"
                    }
                    val teacherAdapter = ArrayAdapter(this@ReportActivity, android.R.layout.simple_dropdown_item_1line, teacherNames)
                    acTeacherFilter.setAdapter(teacherAdapter)
                    acTeacherFilter.threshold = 0
                    acTeacherFilter.setOnClickListener { acTeacherFilter.showDropDown() }

                    acTeacherFilter.setOnItemClickListener { _, _, position, _ ->
                        // AutoComplete فهرستِ فیلترشدهٔ خودش را دارد؛ استفاده از list[position]
                        // بعد از تایپ نام، شناسهٔ معلم دیگری را می‌فرستاد.
                        val selectedText = teacherAdapter.getItem(position).orEmpty()
                        selectedTeacherId = Regex("\\((\\d+)\\)$").find(selectedText)?.groupValues?.getOrNull(1)?.toIntOrNull()
                    }
                    acTeacherFilter.setOnFocusChangeListener { _, hasFocus ->
                        if (hasFocus) acTeacherFilter.showDropDown()
                        else if (selectedTeacherId == null) acTeacherFilter.setText("", false)
                    }
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@ReportActivity, getString(R.string.rpt_tutors_error), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun exportFinancialReport() {
        val month = acMonthFilter.text.toString().trim().toIntOrNull() ?: 12
        val year = acYearFilter.text.toString().trim().toIntOrNull() ?: 1405
        val start = "$year/${String.format(java.util.Locale.US, "%02d", month)}/01"
        val lastDay = if (month <= 6) 31 else if (month <= 11) 30 else 29
        val end = "$year/${String.format(java.util.Locale.US, "%02d", month)}/$lastDay"
        val teacherId = if (rbScopeTeacher.isChecked && currentUserRole != "teacher") selectedTeacherId else null
        val teacherQuery = teacherId?.let { "&teacher_id=$it" } ?: ""
        val baseUrl = RetrofitClient.getInstance(this).baseUrl().toString()
        val url = "${baseUrl}reports/financial/excel?start_date=$start&end_date=$end$teacherQuery"
        ReportExporter.exportToExcel(
            context = this,
            endpointUrl = url,
            fileName = "financial_report_${System.currentTimeMillis()}.xlsx",
            onStart = { Toast.makeText(this, "در حال ساخت خروجی Excel…", Toast.LENGTH_SHORT).show() },
            onComplete = { Toast.makeText(this, "خروجی Excel آماده و قابل اشتراک‌گذاری شد", Toast.LENGTH_LONG).show() },
            onError = { error -> Toast.makeText(this, "خروجی Excel ناموفق بود: $error", Toast.LENGTH_LONG).show() }
        )
    }

    private fun setReportStatus(message: String?, isError: Boolean = false) {
        tvReportStatus?.let { status ->
            if (message.isNullOrBlank()) {
                status.visibility = View.GONE
            } else {
                status.text = message
                status.setTextColor(
                    UiColors.resolve(
                        this,
                        if (isError) R.color.ds_danger else R.color.ds_text_secondary
                    )
                )
                status.visibility = View.VISIBLE
            }
        }
    }

    private fun fetchReport(scope: String) {
        // اگر کاربر نام را تایپ کرده ولی روی suggestion نزده، شناسهٔ انتهای متن
        // (`نام معلم (id)`) را هم resolve کن؛ گزارش نباید بی‌دلیل با «معلم انتخاب نشده» متوقف شود.
        if (scope == "teacher" && currentUserRole != "teacher" && selectedTeacherId == null) {
            selectedTeacherId = Regex("\\((\\d+)\\)$").find(acTeacherFilter.text.toString().trim())
                ?.groupValues?.getOrNull(1)?.toIntOrNull()
        }
        val yearStr = acYearFilter.text.toString().trim()
        val monthStr = acMonthFilter.text.toString().trim()

        val yearVal = yearStr.toIntOrNull()
        val monthVal = monthStr.toIntOrNull()

        if (scope == "teacher" && currentUserRole != "teacher" && selectedTeacherId == null) {
            Toast.makeText(this, getString(R.string.rpt_pick_tutor), Toast.LENGTH_SHORT).show()
            return
        }

        // Keep a visible state on the page; a Toast alone made failed reports
        // look like permanently blank number cards.
        setReportStatus("در حال دریافت ارقام گزارش...", isError = false)
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.

        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val summary = api.getFinancialSummary(
                    userType = scope,
                    teacherId = if (currentUserRole == "teacher") null else selectedTeacherId,
                    year = yearVal,
                    month = monthVal
                )

                withContext(Dispatchers.Main) {
                    setReportStatus(null)
                    tvMonthlyTitle.text = getString(R.string.rpt_monthly_title, yearStr, monthStr)
                    tvMonthlyTotal.text = getString(R.string.common_toman_format, summary.monthly.total)
                    tvMonthlyCollected.text = getString(R.string.common_toman_format, summary.monthly.collected)
                    tvMonthlyUncollected.text = getString(R.string.common_toman_format, summary.monthly.uncollected)

                    // توضیح صفر بودن/پیش‌پرداخت‌ها (فقط نمایش؛ اعداد بالا دست‌نخورده‌اند)
                    ReportHints.bind(this@ReportActivity, tvReportHint, summary.monthly, summary.diagnostics)

                    // O-10: هشدار «پول بی‌تاریخ» — مبلغی که در جمع‌های ماه/سالِ بالا نیست.
                    val undatedAmount = summary.undated_amount ?: 0L
                    val undatedCount = summary.undated_count ?: 0
                    tvUndatedWarning?.let { warning ->
                        if (undatedAmount > 0) {
                            warning.text = getString(
                                R.string.rpt_undated_warning,
                                String.format("%,d", undatedCount),
                                String.format("%,d", undatedAmount)
                            )
                            warning.visibility = View.VISIBLE
                        } else {
                            warning.visibility = View.GONE
                        }
                    }

                    if (scope == "teacher") {
                        cardYearlySummary.visibility = View.VISIBLE
                        tvYearlyTitle.text = getString(R.string.rpt_yearly_title, yearStr)
                        tvYearlyTotal.text = getString(R.string.common_toman_format, summary.yearly.total)
                        tvYearlyCollected.text = getString(R.string.common_toman_format, summary.yearly.collected)
                        tvYearlyUncollected.text = getString(R.string.common_toman_format, summary.yearly.uncollected)
                    } else {
                        cardYearlySummary.visibility = View.GONE
                    }
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    val detail = e.message?.takeIf { it.isNotBlank() } ?: getString(R.string.rpt_calc_error)
                    setReportStatus("گزارش بارگذاری نشد: $detail", isError = true)
                    tvReportHint?.visibility = View.GONE   // توضیح قدیمی کنار خطای تازه نماند
                    Toast.makeText(this@ReportActivity, detail, Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    private fun performStudentSearch() {
        val query = etStudentSearchName.text.toString().trim()
        if (query.isEmpty()) {
            Toast.makeText(this, getString(R.string.rpt_enter_name), Toast.LENGTH_SHORT).show()
            return
        }

        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.

        lifecycleScope.launch(Dispatchers.IO) {
            try {
                // جستجوی چندمنظوره دانش‌آموزان
                val results = api.searchAdvanced(query)
                val studentsOnly = results.filter { it.type == "student" }

                withContext(Dispatchers.Main) {
                    if (studentsOnly.isEmpty()) {
                        Toast.makeText(this@ReportActivity, getString(R.string.rpt_student_nf), Toast.LENGTH_LONG).show()
                        llStatementResult.visibility = View.GONE
                    } else if (studentsOnly.size == 1) {
                        val stId = studentsOnly[0].student_id ?: studentsOnly[0].id
                        fetchStudentStatement(stId)
                    } else {
                        // انتخاب از میان لیست چندتایی
                        showMultipleStudentsDialog(studentsOnly)
                    }
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@ReportActivity, getString(R.string.rpt_search_error), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun showMultipleStudentsDialog(list: List<SearchStudentItem>) {
        val names = list.map { "${it.title} - ${it.subtitle}" }.toTypedArray()
        AlertDialog.Builder(this)
            .setTitle(getString(R.string.rpt_pick_title))
            .setItems(names) { _, which ->
                val selected = list[which]
                val stId = selected.student_id ?: selected.id
                fetchStudentStatement(stId)
            }
            .setNegativeButton(getString(R.string.common_cancel), null)
            .show()
    }

    private fun fetchStudentStatement(studentId: Int) {
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val stmt = api.getStudentStatement(studentId)
                withContext(Dispatchers.Main) {
                    currentStudentIdForPrint = studentId
                    llStatementResult.visibility = View.VISIBLE
                    tvStatementStudentName.text = getString(R.string.rpt_stmt_name, stmt.student_name)
                    tvStatementStudentCode.text = getString(R.string.rpt_stmt_code, stmt.student_code)
                    tvStatementStudentName.setOnClickListener {
                        startActivity(Intent(this@ReportActivity, StudentProfileActivity::class.java).apply {
                            putExtra("STUDENT_ID", studentId)
                        })
                    }
                    // Prefer the new class-scoped totals; old servers fall back to
                    // the legacy aggregate fields without breaking the screen.
                    val classPaidInstitute = stmt.class_paid_institute ?: stmt.total_paid_institute
                    val classDebtInstitute = stmt.class_debt_institute ?: stmt.total_debt_institute
                    tvStatementPaid.text = getString(R.string.common_toman_format, classPaidInstitute)
                    tvStatementDebt.text = getString(R.string.common_toman_format, classDebtInstitute)
                    val teacherLines = stmt.teachers.joinToString("\n") { item ->
                        val teacher = item.teacher_name ?: "بدون معلم"
                        val course = item.course_title ?: "بدون کلاس / بدهی عمومی"
                        val teacherDebt = String.format(java.util.Locale.US, "%,d", item.debt_teacher)
                        val instituteDebt = String.format(java.util.Locale.US, "%,d", item.debt_institute)
                        val totalDebt = String.format(java.util.Locale.US, "%,d", item.debt)
                        "$teacher / $course — بدهی معلم: $teacherDebt، بدهی آموزشگاه: $instituteDebt، کل: $totalDebt تومان"
                    }
                    tvStatementTeacher.text = if (teacherLines.isNotBlank()) teacherLines else
                        "معلم بدهکار: ${stmt.teacher_name ?: "بدون معلم"}"
                    tvStatementTeacher.setOnClickListener {
                        val teacherRows = stmt.teachers.filter { it.teacher_id != null }
                        if (teacherRows.isEmpty()) return@setOnClickListener
                        val labels = teacherRows.map {
                            "${it.teacher_name ?: "بدون معلم"} | بدهی معلم: ${it.debt_teacher} | بدهی آموزشگاه: ${it.debt_institute}"
                        }.toTypedArray()
                        AlertDialog.Builder(this@ReportActivity)
                            .setTitle("انتخاب معلم برای مشاهده پروفایل")
                            .setItems(labels) { _, which ->
                                teacherRows[which].teacher_id?.let { teacherId ->
                                    startActivity(Intent(this@ReportActivity, TeacherProfileActivity::class.java).apply {
                                        putExtra("TEACHER_ID", teacherId)
                                    })
                                }
                            }
                            .setNegativeButton(getString(R.string.common_cancel), null)
                            .show()
                    }
                    tvStatementNextDue.text = stmt.next_installment?.let {
                        "قسط بعدی: ${it.due_date ?: "نامشخص"} | ${it.remaining_amount ?: it.amount ?: 0} تومان"
                    } ?: "قسط بازی ندارد"
                    tvStatementTimeline.text = stmt.payment_timeline.joinToString("\n") {
                        "${it.date ?: "تاریخ نامشخص"} — ${it.amount ?: 0} تومان"
                    }.ifEmpty { "تاریخچه پرداختی وجود ندارد" }
                    btnStatementPay.visibility = if (stmt.next_installment != null) View.VISIBLE else View.GONE
                    btnStatementPay.setOnClickListener {
                        // گزارش می‌تواند چند enrollment داشته باشد؛ ابتدا کلاس را انتخاب می‌کنیم
                        // تا prefill بدهی و enrollment_id همیشه از همان ردیف بیاید.
                        val teacherRows = stmt.teachers
                        if (teacherRows.isEmpty()) {
                            Toast.makeText(this@ReportActivity, "برای پرداخت، کلاس فعالی وجود ندارد", Toast.LENGTH_LONG).show()
                            return@setOnClickListener
                        }
                        val labels = teacherRows.map { row ->
                            "${row.course_title ?: "بدون کلاس"} — معلم ${row.teacher_name ?: "بدون معلم"}"
                        }.toTypedArray()
                        fun openSelected(row: StudentStatementTeacher) {
                            val enrollmentId = row.enrollment_id
                            if (enrollmentId == null || enrollmentId <= 0) {
                                Toast.makeText(this@ReportActivity, "برای بدهی بدون کلاس امکان ثبت پرداخت کلاس‌محور وجود ندارد", Toast.LENGTH_LONG).show()
                                return
                            }
                            startActivity(Intent(this@ReportActivity, InvoiceActivity::class.java).apply {
                                putExtra(InvoiceActivity.EXTRA_IS_ADMIN, true)
                                putExtra(InvoiceActivity.EXTRA_PREFILL_STUDENT_ID, studentId)
                                putExtra(InvoiceActivity.EXTRA_PREFILL_STUDENT_NAME, stmt.student_name)
                                putExtra(InvoiceActivity.EXTRA_PREFILL_CLASS_NAME, labels[teacherRows.indexOf(row)])
                                putExtra(InvoiceActivity.EXTRA_PREFILL_DEBT, row.debt)
                                putExtra(InvoiceActivity.EXTRA_PREFILL_DEBT_TEACHER, row.debt_teacher)
                                putExtra(InvoiceActivity.EXTRA_PREFILL_DEBT_INSTITUTE, row.debt_institute)
                                putExtra(InvoiceActivity.EXTRA_PREFILL_ENROLLMENT_ID, enrollmentId)
                                putExtra(InvoiceActivity.EXTRA_PREFILL_COURSE_ID, row.course_id ?: -1)
                            })
                        }
                        if (teacherRows.size == 1) {
                            openSelected(teacherRows[0])
                        } else {
                            AlertDialog.Builder(this@ReportActivity)
                                .setTitle("انتخاب کلاس برای ثبت پرداخت")
                                .setItems(labels) { _, which -> openSelected(teacherRows[which]) }
                                .setNegativeButton(getString(R.string.common_cancel), null)
                                .show()
                        }
                    }
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@ReportActivity, getString(R.string.rpt_stmt_error), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun printStatementDirect(studentId: Int) {
        Toast.makeText(this, getString(R.string.rpt_rendering), Toast.LENGTH_SHORT).show()
        
        val webView = WebView(this)
        webView.webViewClient = object : WebViewClient() {
            override fun onPageFinished(view: WebView, url: String) {
                val printManager = getSystemService(Context.PRINT_SERVICE) as PrintManager
                val printAdapter = webView.createPrintDocumentAdapter("Kharazmi_Student_Statement")
                val jobName = getString(R.string.rpt_job_name)
                printManager.print(jobName, printAdapter, PrintAttributes.Builder().build())
            }
        }

        val token = SecureLoginStore.getToken(this)  // FIX M22: توکن از حافظه‌ی رمزشده.
        val headers = HashMap<String, String>()
        if (token.isNotEmpty()) {
            headers["Authorization"] = "Bearer $token"
        }

        val retrofit = RetrofitClient.getInstance(this)
        val baseUrl = retrofit.baseUrl().toString()
        val url = "${baseUrl}reports/student_statement/print?student_id=$studentId"

        webView.loadUrl(url, headers)
    }
}
