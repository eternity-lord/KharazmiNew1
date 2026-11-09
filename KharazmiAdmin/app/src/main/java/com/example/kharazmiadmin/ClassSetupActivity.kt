package com.example.kharazmiadmin

import android.content.Intent
import android.os.Bundle
import android.text.Editable
import android.text.TextWatcher
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.ArrayAdapter
import android.widget.AutoCompleteTextView
import android.widget.Button
import android.widget.EditText
import android.widget.ImageButton
import android.widget.TextView
import android.widget.Toast
import android.widget.CheckBox
import android.widget.LinearLayout
import android.content.Context
import androidx.appcompat.app.AlertDialog
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Query
import retrofit2.http.Path
import retrofit2.HttpException
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

// ==========================================
// API Interface Specific to this Activity
// ==========================================
interface ClassSetupNetworkApi {
    @GET("students/search_simple")
    suspend fun searchStudents(@Query("query") q: String): List<StudentSearchItem>

    @POST("enrollments/add")
    suspend fun addEnrollment(@Body data: AddStudentToClassData): AddStudentResponse

    @POST("enrollments/add_bulk")
    suspend fun addEnrollmentsBulk(@Body data: BulkEnrollmentData): BulkEnrollmentResponse

    @GET("classes/{id}/full_report")
    suspend fun getClassReport(@Path("id") id: Int): FullClassReport
}

interface ClassListApi {
    @GET("classes/{id}/details")
    suspend fun getClassDetails(@Path("id") id: Int): ClassDetailsResponse
}


class ClassSetupActivity : BaseActivity() {
    private var isSuspended: Boolean = false

    private var classId: Int = -1
    private var className: String = ""

    // FIX(search): نتایج آخرین جست‌وجو — کلیک handler از id واقعی API استفاده می‌کند (نه parse متن)
    private var searchResults: List<StudentSearchItem> = emptyList()
    private var searchRequestSeq = 0
    private lateinit var rv: RecyclerView
    private lateinit var api: ClassSetupNetworkApi
    private lateinit var listApi: ClassListApi
    private lateinit var invoiceApi: InvoiceApi
    private var currentStudentsList: List<StudentItem> = emptyList() // جدید 🆕

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_class_setup)

        classId = intent.getIntExtra("CLASS_ID", -1)
        className = intent.getStringExtra("CLASS_NAME") ?: ""
        isSuspended = intent.getBooleanExtra("IS_SUSPENDED", false)
        findViewById<TextView>(R.id.tvHeaderTitle).text = getString(R.string.csetup_header, className)

        rv = findViewById(R.id.rvAddedStudents)
        rv.layoutManager = LinearLayoutManager(this)

        val retrofit = RetrofitClient.getInstance(this)
        api = retrofit.create(ClassSetupNetworkApi::class.java)
        listApi = retrofit.create(ClassListApi::class.java)
        invoiceApi = retrofit.create(InvoiceApi::class.java)

        findViewById<Button>(R.id.btnAddStudent).setOnClickListener {
            showAddDialog()
        }

        findViewById<Button>(R.id.btnFinalizeClass).setOnClickListener {
            finalizeClassFlow()
        }

        refreshStudentList()
    }

    private fun finalizeClassFlow() {
        if (currentStudentsList.isEmpty()) {
            AlertDialog.Builder(this)
                .setTitle(getString(R.string.csetup_empty_title))
                .setMessage(getString(R.string.csetup_empty_msg))
                .setPositiveButton(getString(R.string.btn_dismiss), null)
                .show()
            return
        }

        val confirmDialog = AlertDialog.Builder(this)
            .setTitle(getString(R.string.csetup_confirm_title))
            .setMessage(getString(R.string.csetup_confirm_msg))
            .setPositiveButton(getString(R.string.common_yes)) { _, _ -> showClassSummaryPage() }
            .setNegativeButton(getString(R.string.common_no), null)
            .create()

        confirmDialog.show()
        // رنگ‌بندی دکمه‌ها به سبز و قرمز متریال
        confirmDialog.getButton(AlertDialog.BUTTON_POSITIVE).setTextColor(UiColors.resolve(this@ClassSetupActivity, R.color.status_success))
        confirmDialog.getButton(AlertDialog.BUTTON_NEGATIVE).setTextColor(UiColors.resolve(this@ClassSetupActivity, R.color.status_danger))
    }

    private fun showClassSummaryPage() {
        val retrofit = RetrofitClient.getInstance(this)
        val detailsApi = retrofit.create(ClassDetailApi::class.java)

        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.

        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val fullReport = detailsApi.getClassReport(classId)
                val studentsFull = detailsApi.getClassStudentsFull(classId)

                withContext(Dispatchers.Main) {
                    val teacherName = fullReport.info.teacher_name
                    val gradeLevel = getString(R.string.csetup_grade_unknown)
                    val totalStudents = studentsFull.students.size
                    val studentNames = studentsFull.students.joinToString("، ") { it.student_name }
                    
                    val teacherPrice = studentsFull.students.firstOrNull()?.total_tuition ?: 0L
                    val instituteShare = fullReport.info.total_revenue // سهم حدودی آموزشگاه

                    val summaryMessage = """
                        |${getString(R.string.csetup_sum_teacher, teacherName)}
                        |${getString(R.string.csetup_sum_grade, gradeLevel)}
                        |${getString(R.string.csetup_sum_count, totalStudents)}
                        |${getString(R.string.csetup_sum_names, studentNames)}
                        |${getString(R.string.csetup_sum_tprice, String.format("%,d", teacherPrice))}
                        |${getString(R.string.csetup_sum_iprice, String.format("%,d", instituteShare))}
                    """.trimMargin()

                    val summaryDialog = AlertDialog.Builder(this@ClassSetupActivity)
                        .setTitle(getString(R.string.csetup_sum_title))
                        .setMessage(summaryMessage)
                        .setPositiveButton(getString(R.string.csetup_sum_send)) { _, _ ->
                            // FIX (گروه۳/آیتم۱۵): «رفتن به کلاس‌های منتظر تایید» معلم را به
                            // `PendingClassesActivity` می‌برد؛ آن صفحه صفِ **تأیید ادمین** است
                            // (رد/تایید کلاس‌ها) و در پنل معلم معنایی ندارد ⇒ دکمهٔ میانی فقط
                            // برای ادمین ساخته می‌شود. پیام و دکمهٔ «باشه» برای همه می‌ماند.
                            // چک نقش، همان الگوی موجودِ این فایل است (UserCreds → USER_SUB_ROLE؛
                            // در آداپتر دانش‌آموزانِ همین Activity دکمهٔ حذف برای منشی GONE می‌شود).
                            val credsPrefs = getSharedPreferences("UserCreds", Context.MODE_PRIVATE)
                            val subRole = credsPrefs.getString("USER_SUB_ROLE", "admin") ?: "admin"

                            val sentDialogBuilder = AlertDialog.Builder(this@ClassSetupActivity)
                                .setTitle(getString(R.string.csetup_sent_title))
                                .setMessage(getString(R.string.csetup_sent_msg))
                                .setPositiveButton(getString(R.string.common_ok)) { _, _ ->
                                    finish()
                                }
                                .setCancelable(false)

                            if (subRole == "admin") {
                                sentDialogBuilder.setNeutralButton(getString(R.string.csetup_sent_go)) { _, _ ->
                                    val intent = Intent(this@ClassSetupActivity, PendingClassesActivity::class.java)
                                    startActivity(intent)
                                    finish()
                                }
                            }

                            sentDialogBuilder.show()
                        }
                        .setNegativeButton(getString(R.string.csetup_sent_edit), null)
                        .create()

                    summaryDialog.show()
                    summaryDialog.getButton(AlertDialog.BUTTON_POSITIVE).setTextColor(UiColors.resolve(this@ClassSetupActivity, R.color.status_success))
                    summaryDialog.getButton(AlertDialog.BUTTON_NEGATIVE).setTextColor(UiColors.resolve(this@ClassSetupActivity, R.color.status_danger))
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                android.util.Log.e("ClassSetupActivity", "showClassSummaryPage failed", e)
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@ClassSetupActivity, getString(R.string.csetup_sum_error), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun showAddDialog() {
        val view = LayoutInflater.from(this).inflate(R.layout.dialog_search_student, null)
        val acSearch = view.findViewById<AutoCompleteTextView>(R.id.acStudentSearch)
        val tvInfo = view.findViewById<TextView>(R.id.tvSelectedInfo)
        val multiSelectContainer = view.findViewById<LinearLayout>(R.id.llStudentMultiSelect)
        val bulkSelectionSummary = view.findViewById<TextView>(R.id.tvBulkSelectionSummary)
        val selectedStudentIds = linkedSetOf<Int>()

        // فیلدهای جدید تخفیف و شهریه پایه
        val etBaseTuition = view.findViewById<EditText>(R.id.etBaseTuition)
        val acDiscountType = view.findViewById<AutoCompleteTextView>(R.id.acDiscountType)
        val etDiscountValue = view.findViewById<EditText>(R.id.etDiscountValue)
        val tvFinalTuitionPreview = view.findViewById<TextView>(R.id.tvFinalTuitionPreview)

        var selectedId = -1

        // تنظیم گزینه‌های نوع تخفیف
        val discountTypes = arrayOf("بدون تخفیف", "درصدی", "مبلغ ثابت")
        val discountAdapter = ArrayAdapter(this, android.R.layout.simple_dropdown_item_1line, discountTypes)
        acDiscountType.setAdapter(discountAdapter)
        acDiscountType.setText("بدون تخفیف", false)

        // فرمول پیش‌نمایش لحظه‌ای شهریه نهایی
        val updatePreview = {
            val baseTuitionStr = etBaseTuition.text.toString().trim()
            val baseTuition = baseTuitionStr.toIntOrNull()

            if (baseTuition == null || baseTuitionStr.isEmpty()) {
                tvFinalTuitionPreview.text = getString(R.string.csetup_preview_dash)
            } else {
                val dType = when (acDiscountType.text.toString()) {
                    "درصدی" -> "percentage"
                    "مبلغ ثابت" -> "fixed"
                    else -> "none"
                }
                val dVal = etDiscountValue.text.toString().toIntOrNull() ?: 0

                val discountAmt = when (dType) {
                    "percentage" -> (baseTuition * dVal) / 100
                    "fixed" -> dVal
                    else -> 0
                }
                val finalTuition = Math.max(0, baseTuition - discountAmt)
                tvFinalTuitionPreview.text = getString(R.string.sreg_tuition_preview, String.format(Locale("en", "US"), "%,d", finalTuition))
            }
        }

        etBaseTuition.addTextChangedListener(object : TextWatcher {
            override fun afterTextChanged(s: Editable?) { updatePreview() }
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {}
        })

        etDiscountValue.addTextChangedListener(object : TextWatcher {
            override fun afterTextChanged(s: Editable?) { updatePreview() }
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {}
        })

        acDiscountType.setOnItemClickListener { _, _, _, _ ->
            updatePreview()
        }

        // سرچ زنده دانش‌آموز
        // FIX(search): debounce 300ms — تا تایپ آرام نشود request نمی‌رود (قبلاً برای هر کاراکتر)
        var pendingSearch: Runnable? = null
        acSearch.addTextChangedListener(object : TextWatcher {
            override fun afterTextChanged(s: Editable?) {
                val q = s.toString().trim()
                pendingSearch?.let { view.removeCallbacks(it) }
                if (q.length >= 2) {
                    val captured = q
                    val runnable = Runnable {
                        searchServer(captured, acSearch, multiSelectContainer, selectedStudentIds, bulkSelectionSummary)
                    }
                    pendingSearch = runnable
                    view.postDelayed(runnable, 300L)
                }
            }
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {}
        })

        acSearch.setOnItemClickListener { _, _, position, _ ->
            // FIX(search): id واقعی از response API — parse شکننده از متن نمایشی حذف شد
            val item = searchResults.getOrNull(position) ?: return@setOnItemClickListener
            selectedId = item.id
            tvInfo.text = "${item.name} (${item.id})"
        }

        val cbSplitInstallments = view.findViewById<CheckBox>(R.id.cbSplitInstallments)

        AlertDialog.Builder(this)
            .setTitle(getString(R.string.csetup_search_title))
            .setView(view)
            .setPositiveButton(getString(R.string.csetup_search_add)) { _, _ ->
                val baseTuition = etBaseTuition.text.toString().toIntOrNull() ?: 0
                val dType = when (acDiscountType.text.toString()) {
                    "درصدی" -> "percentage"
                    "مبلغ ثابت" -> "fixed"
                    else -> "none"
                }
                val dVal = etDiscountValue.text.toString().toIntOrNull() ?: 0

                // اعتبارسنجی کلاینت‌ساید
                if (baseTuition < 0) {
                    Toast.makeText(this, getString(R.string.csetup_tuition_neg), Toast.LENGTH_SHORT).show()
                    return@setPositiveButton
                }
                if (dType == "percentage" && (dVal < 0 || dVal > 100)) {
                    Toast.makeText(this, getString(R.string.csetup_disc_range), Toast.LENGTH_SHORT).show()
                    return@setPositiveButton
                }
                if (dType == "fixed" && (dVal < 0 || dVal > baseTuition)) {
                    Toast.makeText(this, getString(R.string.csetup_disc_over), Toast.LENGTH_SHORT).show()
                    return@setPositiveButton
                }

                // قسط‌بندی در صورت تیک خوردن
                var installmentList: List<InstallmentCreate>? = null
                if (cbSplitInstallments.isChecked) {
                    val discountAmt = when (dType) {
                        "percentage" -> (baseTuition * dVal) / 100
                        "fixed" -> dVal
                        else -> 0
                    }
                    val finalTuition = Math.max(0, baseTuition - discountAmt)
                    // شهریهٔ صفر قسط ندارد؛ دو قسط صفر از InstallmentCreate رد می‌شوند و
                    // خطای ثبت دانش‌آموز را به‌اشتباه به شهریه نسبت می‌دهند.
                    if (finalTuition > 0) {
                        // FIX: برای مبلغ ۱ هم هیچ قسط صفر ارسال نشود.
                        val todayDate = JalaliUtils.todayJalaliString()
                        val futureDate = getFutureDateString(30)
                        installmentList = if (finalTuition == 1) {
                            listOf(InstallmentCreate(1, todayDate))
                        } else {
                            val half1 = finalTuition / 2
                            val half2 = finalTuition - half1
                            listOf(
                                InstallmentCreate(half1, todayDate),
                                InstallmentCreate(half2, futureDate)
                            )
                        }
                    }
                }

                val selectedIds = if (selectedStudentIds.isNotEmpty()) {
                    selectedStudentIds.toList()
                } else if (selectedId != -1) {
                    listOf(selectedId)
                } else {
                    emptyList()
                }

                when {
                    selectedIds.isEmpty() -> Toast.makeText(this, getString(R.string.csetup_no_pick), Toast.LENGTH_SHORT).show()
                    selectedIds.size == 1 -> addToClass(selectedIds.first(), baseTuition, dType, dVal, installmentList)
                    else -> addMultipleToClass(selectedIds, baseTuition, dType, dVal, installmentList)
                }
            }
            .setNegativeButton(getString(R.string.common_cancel), null)
            .show()
    }

    private fun getFutureDateString(daysAhead: Int): String {
        // FIX H3-B2: real Jalali conversion via JalaliUtils (was year-621 approximation).
        return JalaliUtils.jalaliStringDaysFromNow(daysAhead)
    }

    private fun searchServer(
        query: String,
        ac: AutoCompleteTextView,
        multiSelectContainer: LinearLayout? = null,
        selectedStudentIds: MutableSet<Int>? = null,
        bulkSelectionSummary: TextView? = null
    ) {
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        // FIX(search): شمارنده‌ی نسلی — پاسخِ request کهنه (تایپ سریع) بی‌اثر می‌شود
        val requestId = ++searchRequestSeq
        lifecycleScope.launch(Dispatchers.IO) {
            val fetched: List<StudentSearchItem>? = try {
                api.searchStudents(query)
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                android.util.Log.e("ClassSetupActivity", "searchServer failed", e)
                null
            }
            withContext(Dispatchers.Main) {
                if (requestId != searchRequestSeq) return@withContext // درخواست تازه‌تری آمده → رد
                if (fetched == null) {
                    // FIX(search): خطای شبکه/API — dropdown خالی + پیام قابل فهم
                    searchResults = emptyList()
                    ac.setAdapter(ArrayAdapter(this@ClassSetupActivity, android.R.layout.simple_dropdown_item_1line, listOf(getString(R.string.csetup_search_error))))
                    Toast.makeText(this@ClassSetupActivity, getString(R.string.csetup_search_error), Toast.LENGTH_SHORT).show()
                    return@withContext
                }
                searchResults = fetched
                // FIX(search): حالت خالی مشخص — ردیف «یافت نشد» غیرقابل‌انتخاب است
                val names = if (fetched.isEmpty()) listOf(getString(R.string.csetup_search_empty))
                            else fetched.map { "${it.name} (${it.id})" }
                ac.setAdapter(ArrayAdapter(this@ClassSetupActivity, android.R.layout.simple_dropdown_item_1line, names))
                ac.showDropDown()
                if (multiSelectContainer != null && selectedStudentIds != null && bulkSelectionSummary != null) {
                    renderStudentChoices(fetched, multiSelectContainer, selectedStudentIds, bulkSelectionSummary)
                }
            }
        }
    }

    private fun renderStudentChoices(
        students: List<StudentSearchItem>,
        container: LinearLayout,
        selectedIds: MutableSet<Int>,
        summary: TextView
    ) {
        container.removeAllViews()
        container.visibility = if (students.isEmpty()) View.GONE else View.VISIBLE
        students.forEach { student ->
            val checkBox = CheckBox(this)
            checkBox.text = "${student.name} (${student.id})"
            checkBox.tag = student.id
            checkBox.isChecked = selectedIds.contains(student.id)
            checkBox.setOnCheckedChangeListener { _, checked ->
                if (checked) selectedIds.add(student.id) else selectedIds.remove(student.id)
                summary.text = getString(R.string.csetup_bulk_selected, selectedIds.size)
            }
            container.addView(checkBox)
        }
        summary.text = getString(R.string.csetup_bulk_selected, selectedIds.size)
    }

    private fun enrollmentError(error: Exception, fallback: String): String {
        if (error is HttpException) {
            val body = error.response()?.errorBody()?.string().orEmpty()
            val detail = try {
                val value = org.json.JSONObject(body).opt("detail")
                if (value is String) value else value?.toString().orEmpty()
            } catch (_: Exception) { "" }
            if (detail.isNotBlank()) return "$fallback (HTTP ${error.code()}): $detail"
        }
        return "$fallback: ${error.message ?: "خطای شبکه"}"
    }

    private fun addToClass(studentId: Int, baseTuition: Int, dType: String, dVal: Int, installments: List<InstallmentCreate>?) {
        val today = SimpleDateFormat("yyyy/MM/dd", Locale.US).format(Date())

        val data = AddStudentToClassData(
            student_id = studentId,
            course_id = classId,
            register_date = today,
            shift = "-",
            total_tuition = baseTuition,
            paid_amount = 0,
            payment_method = "-",
            receiver = "-",
            discount_type = dType,
            discount_value = dVal,
            installments = installments
        )

        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.

        lifecycleScope.launch(Dispatchers.IO) {
            try {
                if (isSuspended) {
                    withContext(Dispatchers.Main) {
                        Toast.makeText(this@ClassSetupActivity, getString(R.string.common_class_activate), Toast.LENGTH_LONG).show()
                    }
                    return@launch
                }
                val result = api.addEnrollment(data)
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@ClassSetupActivity, getString(R.string.common_ok_msg, result.message), Toast.LENGTH_SHORT).show()
                    
                    // ابطال کش مربوط به کلاس
                    CacheManager.clear(this@ClassSetupActivity, "class_report_$classId")
                    CacheManager.clear(this@ClassSetupActivity, "class_students_full_$classId")
                    
                    refreshStudentList()
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@ClassSetupActivity, enrollmentError(e, getString(R.string.csetup_add_error)), Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    private fun addMultipleToClass(
        studentIds: List<Int>,
        baseTuition: Int,
        dType: String,
        dVal: Int,
        installments: List<InstallmentCreate>?
    ) {
        val data = BulkEnrollmentData(
            student_ids = studentIds,
            course_id = classId,
            register_date = SimpleDateFormat("yyyy/MM/dd", Locale.US).format(Date()),
            shift = "-",
            total_tuition = baseTuition,
            paid_amount = 0,
            payment_method = "-",
            receiver = "-",
            discount_type = dType,
            discount_value = dVal,
            installments = installments
        )

        lifecycleScope.launch(Dispatchers.IO) {
            try {
                if (isSuspended) {
                    withContext(Dispatchers.Main) {
                        Toast.makeText(this@ClassSetupActivity, getString(R.string.common_class_activate), Toast.LENGTH_LONG).show()
                    }
                    return@launch
                }
                val result = api.addEnrollmentsBulk(data)
                withContext(Dispatchers.Main) {
                    val reasons = result.rejected.joinToString("؛ ") { "${it.student_id}: ${it.reason}" }
                    val detail = if (reasons.isEmpty()) "" else "\n$reasons"
                    Toast.makeText(
                        this@ClassSetupActivity,
                        getString(R.string.csetup_bulk_summary, result.added_count, result.rejected_count) + detail,
                        Toast.LENGTH_LONG
                    ).show()
                    CacheManager.clear(this@ClassSetupActivity, "class_report_$classId")
                    CacheManager.clear(this@ClassSetupActivity, "class_students_full_$classId")
                    refreshStudentList()
                }
            } catch (e: Exception) {
                if (e is kotlinx.coroutines.CancellationException) throw e
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@ClassSetupActivity, enrollmentError(e, getString(R.string.csetup_bulk_error)), Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    private fun refreshStudentList() {
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val details = listApi.getClassDetails(classId)
                withContext(Dispatchers.Main) {
                    currentStudentsList = details.students
                    rv.adapter = ClassSetupStudentAdapter(details.students) { item -> promptRemoveStudent(item) }
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                android.util.Log.e("ClassSetupActivity", "refreshStudentList failed", e)
            }
        }
    }

    private fun promptRemoveStudent(item: StudentItem) {
        AlertDialog.Builder(this)
            .setTitle(getString(R.string.csetup_del_title))
            .setMessage(getString(R.string.csetup_del_msg, item.student_name))
            .setPositiveButton(getString(R.string.action_delete)) { _, _ -> removeStudentFromClass(item) }
            .setNegativeButton(getString(R.string.action_cancel), null)
            .show()
    }

    private fun removeStudentFromClass(item: StudentItem) {
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                invoiceApi.deleteEnrollment(item.enrollment_id)
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@ClassSetupActivity, getString(R.string.csetup_del_done, item.student_name), Toast.LENGTH_SHORT).show()
                    
                    // ابطال کش مربوط به کلاس
                    CacheManager.clear(this@ClassSetupActivity, "class_report_$classId")
                    CacheManager.clear(this@ClassSetupActivity, "class_students_full_$classId")
                    
                    refreshStudentList()
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    if (isSuspended) {
                        Toast.makeText(this@ClassSetupActivity, getString(R.string.common_class_activate), Toast.LENGTH_LONG).show()
                    } else {
                        Toast.makeText(this@ClassSetupActivity, getString(R.string.csetup_del_error), Toast.LENGTH_SHORT).show()
                    }
                }
            }
        }
    }
}

class ClassSetupStudentAdapter(
    private val list: List<StudentItem>,
    private val onRemove: (StudentItem) -> Unit
) : RecyclerView.Adapter<ClassSetupStudentAdapter.VH>() {

    class VH(v: View) : RecyclerView.ViewHolder(v) {
        val tvName: TextView = v.findViewById(R.id.tvStudentName)
        val tvDebt: TextView = v.findViewById(R.id.tvStudentDebt)
        val btnRemove: ImageButton = v.findViewById(R.id.btnRemoveStudent)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val v = LayoutInflater.from(parent.context).inflate(R.layout.item_class_setup_student, parent, false)
        return VH(v)
    }

    override fun onBindViewHolder(holder: VH, position: Int) {
        val item = list[position]
        holder.tvName.text = "${position + 1}. ${item.student_name}"
        holder.tvDebt.text = holder.itemView.context.getString(R.string.csetup_debt_row, String.format(Locale("en", "US"), "%,d", item.debt))

        holder.tvName.setOnClickListener {
            val intent = Intent(holder.itemView.context, StudentProfileActivity::class.java)
            intent.putExtra("STUDENT_ID", item.student_id)
            holder.itemView.context.startActivity(intent)
        }

        val context = holder.itemView.context
        val credsPrefs = context.getSharedPreferences("UserCreds", Context.MODE_PRIVATE)
        val subRole = credsPrefs.getString("USER_SUB_ROLE", "admin") ?: "admin"
        if (subRole == "secretary") {
            holder.btnRemove.visibility = View.GONE
        }

        holder.btnRemove.setOnClickListener { onRemove(item) }
    }

    override fun getItemCount() = list.size
}
