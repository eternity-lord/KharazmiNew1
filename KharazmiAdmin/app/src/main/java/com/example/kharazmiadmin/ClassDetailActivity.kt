package com.example.kharazmiadmin

import android.widget.Toast

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.CheckBox
import android.widget.LinearLayout
import android.widget.TextView
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.google.android.material.tabs.TabLayout
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import retrofit2.http.GET
import retrofit2.http.Path
import retrofit2.http.POST
import retrofit2.http.Query
import retrofit2.http.DELETE
import retrofit2.http.PUT
import retrofit2.http.Body
import androidx.appcompat.app.AlertDialog

// مدل‌های داده منطبق با سرور
data class FullClassReport(
    val info: ClassReportInfo,
    val students: List<ClassStudentData>,
    val sessions: List<ClassSessionHistory>
)
data class ClassReportInfo(
    val title: String, val code: String, val teacher_name: String,
    val session_count: Int, val total_students: Int,
    val total_revenue: Long, val total_debt: Long,
    val debt_to_teacher: Long = 0,
    val debt_to_institute: Long = 0
)
data class ClassStudentData(
    val name: String,
    val mobile: String,
    val paid: Long,
    val debt: Long,
    val debt_to_teacher: Long = 0,
    val debt_to_institute: Long = 0,
    val enrollment_id: Int? = null,
    val course_id: Int? = null,
    val course_title: String? = null,
    val teacher_id: Int? = null,
    val teacher_name: String? = null,
    val is_unassigned: Boolean = false
)
// FIX (تاریخچهٔ جلسات): ردیف هر شاگرد داخل یک جلسه (نام حاضر/غایب + برچسب تأخیر/موجه).
// فیلدهای اختیاری‌اند تا کش/پاسخ قدیمی (بدون این کلیدها) صفحه را نشکند.
data class ClassSessionStudent(
    val student_id: Int = 0,
    val name: String = "",
    val student_code: Int? = null,
    val status: String = "Present",  // Present / Late / Absent
    val excused: Boolean = false
)
data class ClassSessionHistory(
    val date: String,
    val present_count: Int,
    val absent_count: Int,
    val session_id: Int? = null,
    val session_code: Int? = null,
    val weekday: String = "",
    val present_students: List<ClassSessionStudent> = emptyList(),
    val absent_students: List<ClassSessionStudent> = emptyList(),
    val total_cost: Long = 0,
    val cost_per_student: Long = 0,
    val start_time: String = "",
    val end_time: String = ""
)

// مدل‌های جدید برای تاریخچه حضور و غیاب دانش‌آموز
data class StudentAttendanceHistoryRequest(val student_id: Int, val course_id: Int)
data class StudentAttendanceHistoryResponse(
    val student_name: String,
    val course_title: String,
    val course_code: String,
    val total_sessions: Int,
    val present_count: Int,
    val absent_count: Int,
    val attendance_rate: Double,
    val attendance_history: List<AttendanceHistoryItem>
)
data class AttendanceHistoryItem(
    val session_id: Int,
    val date: String,
    val status: String,
    val session_cost: Long,
    val attendee_count: Int
)

// مدل برای لیست کامل دانش‌آموزان کلاس
data class ClassStudentsFullResponse(
    val course_info: CourseDetailInfo,
    val students: List<StudentFullItem>
)
data class CourseDetailInfo(
    val id: Int,
    val title: String,
    val code: String,
    val teacher_id: Int,
    val is_suspended: Boolean
)
data class StudentFullItem(
    val student_id: Int,
    val student_name: String,
    val national_code: String,
    val mobile: String,
    val total_tuition: Long,
    val paid: Long,
    val debt: Long,
    val debt_teacher: Long,
    val debt_institute: Long,
    val paid_teacher: Long = 0,
    val paid_institute: Long = 0,
    val wallet_teacher: Long? = 0,
    val wallet_institute: Long? = 0,
    val student_code: Int? = null,
    val present_count: Int,
    val absent_count: Int,
    val total_sessions: Int,
    val attendance_rate: Double,
    val is_suspended: Boolean,
    val enrollment_id: Int,
    val discount_type: String? = "none",
    val discount_value: Int? = 0,
    val discount_amount: Long? = 0,
    // «این بدهی برای چند جلسه‌ی همین کلاس است؟» (nullable: سرور قدیمی نمی‌فرستد)
    val sessions_billed: Int? = null,
    val unpaid_sessions: Int? = null
)

// اینترفیس API
interface ClassDetailApi {
    @GET("classes/{id}/full_report")
    suspend fun getClassReport(@Path("id") id: Int): FullClassReport

    @GET("classes/{id}/students_full")
    suspend fun getClassStudentsFull(@Path("id") id: Int): ClassStudentsFullResponse

    @POST("attendance/student_history")
    suspend fun getStudentAttendanceHistory(@Body req: StudentAttendanceHistoryRequest): StudentAttendanceHistoryResponse
}

data class DeleteClassRequest(val forgive_session_charges: Boolean)

interface ClassDetailActionsApi {
    @DELETE("classes/{course_id}")
    suspend fun deleteClass(
        @Path("course_id") courseId: Int,
        @Query("forgive_session_charges") forgive: Boolean
    ): SimpleResponse

    @POST("classes/{course_id}/request_delete")
    suspend fun requestDeleteClass(
        @Path("course_id") courseId: Int,
        @Body req: DeleteClassRequest
    ): SimpleResponse

    @POST("classes/{course_id}/suspend")
    suspend fun suspendClass(@Path("course_id") courseId: Int): SuspendResponse

    @PUT("classes/update_info/{course_id}")
    suspend fun updateClassInfo(@Path("course_id") courseId: Int, @Body data: ClassUpdateInfo): SimpleResponse

    @PUT("classes/update")
    suspend fun updateClass(@Query("course_id") courseId: Int, @Body data: AdminClassUpdateRequest): SimpleResponse
}

data class ClassUpdateInfo(val title: String, val grade_level: String? = null)

class ClassDetailActivity : BaseActivity() {

    // تغییرات حساس کلاس از یک مسیر ادمین‌محور و قابل audit عبور می‌کند.
    private fun updateClass(request: AdminClassUpdateRequest) {
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                RetrofitClient.getInstance(this@ClassDetailActivity).create(ClassDetailActionsApi::class.java)
                    .updateClass(classId, request)
                withContext(Dispatchers.Main) { Toast.makeText(this@ClassDetailActivity, "کلاس به‌روزرسانی شد", Toast.LENGTH_SHORT).show() }
            } catch (error: Exception) {
                if (error is kotlinx.coroutines.CancellationException) throw error
                withContext(Dispatchers.Main) { Toast.makeText(this@ClassDetailActivity, "ویرایش کلاس انجام نشد", Toast.LENGTH_SHORT).show() }
            }
        }
    }

    private var classId: Int = -1
    private var reportData: FullClassReport? = null
    var studentsFullData: ClassStudentsFullResponse? = null
    private lateinit var tvContent: TextView
    private lateinit var rvStudents: RecyclerView
    private lateinit var studentAdapter: ClassStudentAdapter
    private lateinit var tabLayout: TabLayout
    // FIX (کلاس-مالی/تازگی): اولین onResume بعد از onCreate نباید دوباره fetch کند (onCreate خودش
    // دو فراخوانی تازه دارد)؛ از بازگشت دوم به بعد (از «ثبت حضور و غیاب»، «ثبت‌نام شاگرد»، پروفایل
    // شاگرد و ...) اعداد مالی کلاس دوباره از سرور/کش خوانده می‌شوند.
    private var firstResumeHandled = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_class_detail)

        classId = intent.getIntExtra("CLASS_ID", -1)
        tvContent = findViewById(R.id.tvClassContent)

        // Setup RecyclerView for students
        rvStudents = findViewById(R.id.rvStudents)
        rvStudents.layoutManager = LinearLayoutManager(this)
        studentAdapter = ClassStudentAdapter(emptyList()) { studentId, studentName ->
            // Open student attendance history
            openStudentAttendanceHistory(studentId, studentName)
        }
        rvStudents.adapter = studentAdapter

        // Hide RecyclerView initially, show TextView
        rvStudents.visibility = View.GONE
        tvContent.visibility = View.VISIBLE

        // ۱) دکمه ثبت حضور و غیاب
        findViewById<Button>(R.id.btnGoToAttendance).setOnClickListener {
            if (reportData != null) {
                val intent = Intent(this, AttendanceActivity::class.java)
                intent.putExtra("TARGET_COURSE_ID", classId)
                intent.putExtra("TARGET_COURSE_NAME", reportData!!.info.title)
                startActivity(intent)
            }
        }

        // ۲) دکمه ثبت‌نام و ویرایش تعداد دانش‌آموزان
        findViewById<Button>(R.id.btnClassSetupAction).setOnClickListener {
            if (reportData != null) {
                val intent = Intent(this, ClassSetupActivity::class.java)
                intent.putExtra("CLASS_ID", classId)
                intent.putExtra("CLASS_NAME", reportData!!.info.title)
                startActivity(intent)
            }
        }

        // ۳) دکمه اصلاح عنوان کلاس (فقط عنوان؛ پایه دست نمی‌خورد — رجوع به FIX grade-289)
        findViewById<Button>(R.id.btnEditClassInfoAction).setOnClickListener {
            showEditClassInfoDialog()
        }

        // ۴) دکمه تعلیق کلاس
        // FIX (گروه۳/آیتم۱۳): در پنل معلم، «امور مدیریتی» (= تعلیق کلاس) پنهان می‌شود و
        // فقط «اصلاح اطلاعات کلاس» و «حذف کلاس» می‌ماند؛ حذف برای غیر ادمین از قبل مسیر
        // درستش را می‌رود (showDeleteClassDialog → requestDeleteClass) ⇒ دست نمی‌خورد.
        // تعلیق مستقیماً POST classes/{id}/suspend می‌زند و کار ادمین/منشی است، پس listener
        // هم فقط در شاخهٔ ادمین ثبت می‌شود (دکمهٔ پنهانِ کلیک‌پذیر = راه فرار).
        // همان چک نقش موجود پروژه: `UserCreds` → `USER_SUB_ROLE` (showDeleteClassDialog:334).
        val credsPrefs = getSharedPreferences("UserCreds", Context.MODE_PRIVATE)
        val subRole = credsPrefs.getString("USER_SUB_ROLE", "admin") ?: "admin"
        val btnSuspendAction = findViewById<Button>(R.id.btnSuspendAction)
        if (subRole == "admin") {
            btnSuspendAction.setOnClickListener {
                suspendClass()
            }
        } else {
            btnSuspendAction.visibility = View.GONE
        }

        // ۵) دکمه حذف کلاس (با اعمال قفل مالی انحصاری)
        findViewById<Button>(R.id.btnDeleteClassAction).setOnClickListener {
            showDeleteClassDialog()
        }

        // تنظیم تب‌ها
        tabLayout = findViewById<TabLayout>(R.id.tabLayoutClass)
        tabLayout.addOnTabSelectedListener(object : TabLayout.OnTabSelectedListener {
            override fun onTabSelected(tab: TabLayout.Tab?) {
                updateUI(tab?.position ?: 0)
            }
            override fun onTabUnselected(tab: TabLayout.Tab?) {}
            override fun onTabReselected(tab: TabLayout.Tab?) {}
        })

        // دکمه خروجی اکسل کلاس
        findViewById<Button>(R.id.btnClassExportExcel).setOnClickListener {
            ReportExporter.exportToExcel(
                context = this,
                endpointUrl = "classes/${classId}/students_full/excel",
                fileName = "class_students_${classId}.xlsx",
                onStart = {
                    Toast.makeText(this, getString(R.string.cdetail_excel_downloading), Toast.LENGTH_SHORT).show()
                },
                onComplete = {
                    Toast.makeText(this, getString(R.string.cdetail_excel_done), Toast.LENGTH_SHORT).show()
                },
                onError = { errorMsg ->
                    Toast.makeText(this, getString(R.string.cdetail_excel_error, errorMsg), Toast.LENGTH_LONG).show()
                }
            )
        }

        // دکمه چاپ PDF لیست کلاس
        findViewById<Button>(R.id.btnClassExportPdf).setOnClickListener {
            val data = studentsFullData
            if (data == null || data.students.isEmpty()) {
                Toast.makeText(this, getString(R.string.cdetail_students_not_loaded), Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }

            val headers = listOf(getString(R.string.common_id), getString(R.string.cdetail_th_student), getString(R.string.cdetail_th_tuition), getString(R.string.cdetail_th_paid), getString(R.string.cdetail_th_debt), getString(R.string.cdetail_th_attendance))
            val rows = data.students.map { student ->
                listOf(
                    student.student_id.toString(),
                    student.student_name,
                    String.format("%,d", student.total_tuition),
                    String.format("%,d", student.paid),
                    String.format("%,d", student.debt),
                    "${String.format("%.1f", student.attendance_rate)}%"
                )
            }

            ReportExporter.printPdfReport(
                context = this,
                title = getString(R.string.cdetail_excel_title, reportData?.info?.title ?: ""),
                headers = headers,
                rows = rows
            )
        }

        fetchData()
        fetchStudentsFullData()
    }

    override fun onResume() {
        super.onResume()
        // FIX (کلاس-مالی/تازگی): قبلاً گزارش کلاس فقط یک‌بار در onCreate خوانده می‌شد. با بازگشت از
        // «ثبت حضور و غیاب» (که بدهی/درآمد را عوض می‌کند) باگ‌ها: اطلاعات کلی همان snapshot قدیمی را
        // نشان می‌داد (کاربر بعد از برگزاری جلسه «درآمد وصول شده: 0 / بدهی به معلم: 0 / بدهی به
        // آموزشگاه: 0» می‌دید، در حالی که تب«دانش‌آموزان»/برگهٔ حضور اعداد درست را داشتند). الان مثل
        // ClassManagementActivity/StudentProfileActivity هر بازگشت به صفحه، اعداد را تازه می‌کند.
        if (!firstResumeHandled) {
            firstResumeHandled = true
            return
        }
        fetchData()
        fetchStudentsFullData()
    }

    private fun showEditClassInfoDialog() {
        val view = LayoutInflater.from(this).inflate(R.layout.dialog_ip_input, null)
        val etInput = view.findViewById<android.widget.EditText>(R.id.etIpInput)
        etInput.hint = getString(R.string.cdetail_edit_hint)
        etInput.setText(reportData?.info?.title ?: "")

        AlertDialog.Builder(this)
            .setTitle(getString(R.string.cdetail_edit_title))
            .setView(view)
            .setPositiveButton(getString(R.string.cdetail_edit_save)) { _, _ ->
                val newTitle = etInput.text.toString().trim()
                if (newTitle.isNotEmpty()) {
                    updateClassInfoOnServer(newTitle)
                }
            }
            .setNegativeButton(getString(R.string.common_cancel), null)
            .show()
    }

    private fun updateClassInfoOnServer(newTitle: String) {
        val retrofit = RetrofitClient.getInstance(this)
        val api = retrofit.create(ClassDetailActionsApi::class.java)

        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.

        lifecycleScope.launch(Dispatchers.IO) {
            try {
                // FIX (grade-289): پایه هاردکد «دوازدهم» هر ویرایش عنوان را به خرابی grade_level
                // تبدیل می‌کرد. دیالوگ فقط عنوان می‌گیرد پس grade_level را اصلاً نمی‌فرستیم (null)؛
                // سرور None را «دست نزن» می‌فهمد. (Gson پیش‌فرض null را از JSON حذف می‌کند.)
                val response = api.updateClassInfo(classId, ClassUpdateInfo(newTitle))
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@ClassDetailActivity, getString(R.string.common_ok_msg, response.message), Toast.LENGTH_SHORT).show()
                    fetchData() // Refresh details
                    fetchStudentsFullData()
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@ClassDetailActivity, getString(R.string.cdetail_edit_error), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun suspendClass() {
        val retrofit = RetrofitClient.getInstance(this)
        val api = retrofit.create(ClassDetailActionsApi::class.java)

        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.

        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val response = api.suspendClass(classId)
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@ClassDetailActivity, getString(R.string.common_ok_msg, response.message), Toast.LENGTH_SHORT).show()
                    fetchData() // Refresh
                    fetchStudentsFullData()
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@ClassDetailActivity, getString(R.string.cdetail_suspend_error), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun showDeleteClassDialog() {
        val prefs = getSharedPreferences("UserCreds", Context.MODE_PRIVATE)
        val subRole = prefs.getString("USER_SUB_ROLE", "admin") ?: "admin"
        val checkBox = CheckBox(this).apply {
            text = getString(R.string.cdetail_forgive_check)
            isChecked = true
        }
        val container = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(48, 24, 48, 0)
            addView(checkBox)
        }
        val msg = if (subRole == "admin") {
            getString(R.string.cdetail_del_admin)
        } else {
            getString(R.string.cdetail_del_request)
        }
        val dialog = AlertDialog.Builder(this)
            .setTitle(getString(R.string.cdetail_del_title))
            .setMessage(msg)
            .setView(container)
            .setPositiveButton(getString(R.string.common_delete_yes)) { _, _ ->
                performDeleteClass(subRole, checkBox.isChecked)
            }
            .setNegativeButton(getString(R.string.action_cancel), null)
            .create()

        dialog.show()
        dialog.getButton(AlertDialog.BUTTON_POSITIVE).setTextColor(UiColors.resolve(this@ClassDetailActivity, R.color.status_success))
        dialog.getButton(AlertDialog.BUTTON_NEGATIVE).setTextColor(UiColors.resolve(this@ClassDetailActivity, R.color.status_danger))
    }

    private fun performDeleteClass(subRole: String, forgive: Boolean) {
        val retrofit = RetrofitClient.getInstance(this)
        val api = retrofit.create(ClassDetailActionsApi::class.java)

        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.

        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val message = if (subRole == "admin") {
                    api.deleteClass(classId, forgive).message
                } else {
                    api.requestDeleteClass(classId, DeleteClassRequest(forgive)).message
                }
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@ClassDetailActivity, getString(R.string.common_ok_msg, message), Toast.LENGTH_LONG).show()
                    
                    // ابطال کش مربوط به کلاس
                    CacheManager.clear(this@ClassDetailActivity, "class_report_$classId")
                    CacheManager.clear(this@ClassDetailActivity, "class_students_full_$classId")
                    CacheManager.clearByPrefix(this@ClassDetailActivity, "classes_list")
                    
                    finish() // Close page after deletion
                }
            } catch (e: retrofit2.HttpException) {
                val errorBody = e.response()?.errorBody()?.string()
                val message = if (!errorBody.isNullOrEmpty()) {
                    try {
                        val json = com.google.gson.JsonParser().parse(errorBody).asJsonObject
                        json.get("detail").getAsString()
                    } catch (parseEx: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (parseEx is kotlinx.coroutines.CancellationException) throw parseEx;
                        getString(R.string.cdetail_del_error)
                    }
                } else {
                    getString(R.string.cdetail_del_error)
                }
                withContext(Dispatchers.Main) {
                    // دیالوگ مقتدرانه با جزئیات مبالغ بدهی تفکیک شده
                    AlertDialog.Builder(this@ClassDetailActivity)
                        .setTitle(getString(R.string.cdetail_del_money_title))
                        .setMessage(message)
                        .setPositiveButton(getString(R.string.common_understood), null)
                        .show()
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@ClassDetailActivity, getString(R.string.cdetail_net_error), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun fetchData() {
        val retrofit = RetrofitClient.getInstance(this)
        val api = retrofit.create(ClassDetailApi::class.java)

        val cacheKey = "class_report_" + classId
        val type = object : com.google.gson.reflect.TypeToken<FullClassReport>() {}.type

        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.

        lifecycleScope.launch(Dispatchers.Main) {
            CachedApiCall.execute(
                context = this@ClassDetailActivity,
                cacheKey = cacheKey,
                type = type,
                networkCall = { api.getClassReport(classId) },
                onSuccess = { data, isOffline, timestamp ->
                    reportData = data
                    findViewById<TextView>(R.id.tvPageTitle).text = getString(R.string.cdetail_page_title, data.info.title, data.info.code)
                    // FIX (کلاس-مالی/تازگی): تبِ فعلی دوباره رندر شود، نه پرش اجباری به تب اول؛
                    // وگرنه تازه‌سازی پس‌زمینه (onResume) کاربر را از تب دانش‌آموزان/جلسات بیرون می‌انداخت.
                    updateUI(tabLayout.selectedTabPosition)
                    if (isOffline) {
                        CachedApiCall.showOfflineBanner(this@ClassDetailActivity, timestamp)
                    } else {
                        CachedApiCall.hideOfflineBanner(this@ClassDetailActivity)
                    }
                },
                onFailure = {
                    tvContent.text = getString(R.string.common_offline_empty)
                }
            )
        }
    }

    private fun updateUI(tabIndex: Int) {
        val scrollView = findViewById<View>(R.id.scrollViewContent)
        val tabContainer = findViewById<View>(R.id.llStudentTabContainer)

        when (tabIndex) {
            0 -> { // اطلاعات کلی
                if (reportData == null) return
                val data = reportData!!

                scrollView.visibility = View.VISIBLE
                tabContainer.visibility = View.GONE

                val sb = StringBuilder()
                sb.append(getString(R.string.cdetail_info_name, data.info.title))
                sb.append(getString(R.string.cdetail_info_code, data.info.code))
                sb.append(getString(R.string.cdetail_info_teacher, data.info.teacher_name))
                sb.append(getString(R.string.cdetail_info_sessions, data.info.session_count))
                sb.append(getString(R.string.cdetail_info_students, data.info.total_students))
                sb.append(getString(R.string.cdetail_info_revenue, String.format("%,d", data.info.total_revenue)))
                sb.append(getString(R.string.cdetail_info_debt_teacher, String.format("%,d", data.info.debt_to_teacher)))
                sb.append(getString(R.string.cdetail_info_debt_institute, String.format("%,d", data.info.debt_to_institute)))

                // پرداخت‌ها نیز از همان enrollmentهای کلاس جمع می‌شوند؛ کیف کلی دانش‌آموز
                // عمداً در گزارش کلاس وارد نمی‌شود.
                studentsFullData?.let { fullData ->
                    val totalPaidTeacher = fullData.students.sumOf { it.paid_teacher }
                    val totalPaidInstitute = fullData.students.sumOf { it.paid_institute }
                    
                    sb.append("\n===========================\n")
                    sb.append(getString(R.string.cdetail_fin_teacher_title))
                    sb.append(getString(R.string.cdetail_fin_teacher_paid, String.format("%,d", totalPaidTeacher)))
                    sb.append(getString(R.string.cdetail_fin_inst_title))
                    sb.append(getString(R.string.cdetail_fin_inst_paid, String.format("%,d", totalPaidInstitute)))
                }

                // نمایش وضعیت تعلیق کلاس
                studentsFullData?.let {
                    if (it.course_info.is_suspended) {
                        sb.append(getString(R.string.cdetail_suspended))
                    }
                }

                tvContent.text = sb.toString()
            }
            1 -> { // لیست دانش‌آموزان
                scrollView.visibility = View.GONE
                tabContainer.visibility = View.VISIBLE
                rvStudents.visibility = View.VISIBLE

                // Update students list with full data including attendance
                if (studentsFullData != null) {
                    updateStudentsListWithFullData()
                } else {
                    fetchStudentsFullData()
                }
            }
            2 -> { // تاریخچه جلسات
                if (reportData == null) return
                val data = reportData!!

                scrollView.visibility = View.VISIBLE
                tabContainer.visibility = View.GONE

                val sb = StringBuilder()
                sb.append(getString(R.string.cdetail_hist_title))
                if (data.sessions.isEmpty()) sb.append(getString(R.string.cdetail_hist_empty))

                // FIX (تاریخچهٔ جلسات): سرجمع دوره بالای لیست — یک نگاه، کلِ حضور و غیاب کلاس.
                if (data.sessions.isNotEmpty()) {
                    sb.append(
                        getString(
                            R.string.cdetail_hist_summary,
                            data.sessions.size,
                            data.sessions.sumOf { it.present_count },
                            data.sessions.sumOf { it.absent_count }
                        )
                    )
                }

                data.sessions.forEachIndexed { index, sess ->
                    // FIX (تاریخچهٔ جلسات): روز هفته کنار تاریخ (سرور می‌فرستد؛ اگر پاسخ قدیمی بود،
                    // همین‌جا از تاریخ محاسبه می‌شود) تا «جلسه ۱: 1405/07/07 (دوشنبه)» دیده شود.
                    val weekday = sess.weekday.ifBlank { JalaliUtils.persianWeekdayName(sess.date) }
                    sb.append(
                        if (weekday.isBlank()) {
                            getString(R.string.cdetail_hist_row, index + 1, sess.date)
                        } else {
                            getString(R.string.cdetail_hist_row_weekday, index + 1, sess.date, weekday)
                        }
                    )
                    sb.append(getString(R.string.cdetail_hist_present, sess.present_count))
                    // FIX (تاریخچهٔ جلسات): نام تکی حاضرین/غایبین همین جلسه (خواستهٔ کاربر) —
                    // «فلان دانش‌آموز حاضر، فلان دانش‌آموز غایب» به‌جای فقط تعداد.
                    appendSessionStudents(sb, sess.present_students)
                    sb.append(getString(R.string.cdetail_hist_absent, sess.absent_count))
                    appendSessionStudents(sb, sess.absent_students)
                    // هزینه/ساعت فقط وقتی داده دارد (جلسه‌های قدیمی این‌ها را ندارند).
                    if (sess.total_cost > 0) {
                        sb.append(
                            getString(
                                R.string.cdetail_hist_cost,
                                String.format("%,d", sess.total_cost),
                                String.format("%,d", sess.cost_per_student)
                            )
                        )
                    }
                    if (!sess.start_time.isNullOrBlank()) {
                        sb.append(getString(R.string.cdetail_hist_time, sess.start_time, sess.end_time ?: ""))
                    }
                    sb.append("---------------------------\n")
                }
                tvContent.text = sb.toString()
            }
        }
    }

    /**
     * FIX (تاریخچهٔ جلسات): فهرست نام شاگردان یک جلسه (حاضرین یا غایبین)، هر نفر در یک خط
     * با برچسب «(با تأخیر)» یا «(موجه)». اگر پاسخِ کش‌شده قدیمی باشد و نامی نداشته باشد،
     * خط اضافه‌ای چاپ نمی‌شود و همان شمارش «حاضرین/غایبین» بالا سر جایش می‌ماند.
     */
    private fun appendSessionStudents(sb: StringBuilder, students: List<ClassSessionStudent>) {
        students.forEach { student ->
            if (student.name.isBlank()) return@forEach
            val tag = when {
                student.status == "Late" -> getString(R.string.cdetail_hist_late_tag)
                student.excused -> getString(R.string.cdetail_hist_excused_tag)
                else -> ""
            }
            sb.append(getString(R.string.cdetail_hist_student_row, student.name, tag))
        }
    }

    private fun openStudentProfile(studentId: Int, studentName: String) {
        // Open student profile directly with student ID
        val intent = Intent(this, StudentProfileActivity::class.java)
        intent.putExtra("STUDENT_ID", studentId)
        startActivity(intent)
    }

    private fun openStudentAttendanceHistory(studentId: Int, studentName: String) {
        // Show student attendance history in a dialog
        showStudentAttendanceHistoryDialog(studentId, studentName)
    }

    private fun fetchStudentsWithIds() {
        val retrofit = RetrofitClient.getInstance(this)
        val api = retrofit.create(InvoiceApi::class.java)

        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.

        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val response = api.getClassDetails(classId)
                withContext(Dispatchers.Main) {
                    studentAdapter.updateList(response.students)
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@ClassDetailActivity, getString(R.string.cdetail_students_error), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun fetchStudentsFullData() {
        val retrofit = RetrofitClient.getInstance(this)
        val api = retrofit.create(ClassDetailApi::class.java)

        val cacheKey = "class_students_full_" + classId
        val type = object : com.google.gson.reflect.TypeToken<ClassStudentsFullResponse>() {}.type

        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.

        lifecycleScope.launch(Dispatchers.Main) {
            CachedApiCall.execute(
                context = this@ClassDetailActivity,
                cacheKey = cacheKey,
                type = type,
                networkCall = { api.getClassStudentsFull(classId) },
                onSuccess = { response, isOffline, timestamp ->
                    studentsFullData = response
                    if (tabLayout.selectedTabPosition == 1) {
                        updateStudentsListWithFullData()
                    }
                    if (isOffline) {
                        CachedApiCall.showOfflineBanner(this@ClassDetailActivity, timestamp)
                    } else {
                        CachedApiCall.hideOfflineBanner(this@ClassDetailActivity)
                    }
                },
                onFailure = {
                    Toast.makeText(this@ClassDetailActivity, getString(R.string.common_offline_empty), Toast.LENGTH_SHORT).show()
                }
            )
        }
    }

    private fun updateStudentsListWithFullData() {
        studentsFullData?.let { data ->
            // Convert StudentFullItem to StudentItem for the adapter
            val studentItems = data.students.map { student ->
                StudentItem(
                    student_id = student.student_id,
                    student_name = student.student_name,
                    debt = student.debt,
                    enrollment_id = student.enrollment_id,
                    debt_teacher = student.debt_teacher,
                    debt_institute = student.debt_institute
                )
            }
            if (studentItems.isEmpty()) {
                Toast.makeText(this@ClassDetailActivity, getString(R.string.cdetail_students_empty), Toast.LENGTH_LONG).show()
            }
            studentAdapter.updateList(studentItems)
        }
    }

    private fun showStudentAttendanceHistoryDialog(studentId: Int, studentName: String) {
        val retrofit = RetrofitClient.getInstance(this)
        val api = retrofit.create(ClassDetailApi::class.java)

        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.

        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val response = api.getStudentAttendanceHistory(
                    StudentAttendanceHistoryRequest(student_id = studentId, course_id = classId)
                )

                withContext(Dispatchers.Main) {
                    val dialog = androidx.appcompat.app.AlertDialog.Builder(this@ClassDetailActivity)
                        .setTitle(getString(R.string.cdetail_att_title, studentName))
                        .setMessage(buildAttendanceHistoryMessage(response))
                        .setPositiveButton(getString(R.string.btn_dismiss), null)
                        .setNeutralButton(getString(R.string.cdetail_grade_btn)) { _, _ ->
                            val intent = Intent(this@ClassDetailActivity, SubmitGradeActivity::class.java).apply {
                                putExtra("STUDENT_ID", studentId)
                                putExtra("COURSE_ID", classId)
                                putExtra("STUDENT_NAME", studentName)
                            }
                            startActivity(intent)
                        }
                        .create()
                    dialog.show()
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@ClassDetailActivity, getString(R.string.cdetail_att_error), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun buildAttendanceHistoryMessage(response: StudentAttendanceHistoryResponse): String {
        val sb = StringBuilder()
        sb.append(getString(R.string.cdetail_att_student, response.student_name))
        sb.append(getString(R.string.cdetail_att_class, response.course_title, response.course_code))
        sb.append(getString(R.string.cdetail_att_stats))
        sb.append(getString(R.string.cdetail_att_total, response.total_sessions))
        sb.append(getString(R.string.cdetail_att_present, response.present_count))
        sb.append(getString(R.string.cdetail_att_absent, response.absent_count))
        sb.append(getString(R.string.cdetail_att_rate, String.format("%.1f", response.attendance_rate)))

        sb.append(getString(R.string.cdetail_att_hist))
        if (response.attendance_history.isEmpty()) {
            sb.append(getString(R.string.cdetail_att_no_session))
        } else {
            response.attendance_history.forEachIndexed { index, session ->
                val statusIcon = if (session.status == "حاضر") getString(R.string.cdetail_st_present) else getString(R.string.cdetail_st_absent)
                sb.append("${index + 1}. ${session.date}: $statusIcon ${session.status}\n")
                sb.append(getString(R.string.cdetail_sess_cost, String.format("%,d", session.session_cost)))
                sb.append(getString(R.string.cdetail_sess_attendees, session.attendee_count))
                sb.append("   ---\n")
            }
        }

        return sb.toString()
    }
}

// Adapter for class students with clickable names
class ClassStudentAdapter(
    private var students: List<StudentItem>,
    private val onStudentClick: (Int, String) -> Unit
) : RecyclerView.Adapter<ClassStudentAdapter.StudentViewHolder>() {

    fun updateList(newList: List<StudentItem>) {
        students = newList
        notifyDataSetChanged()
    }

    class StudentViewHolder(view: View) : RecyclerView.ViewHolder(view) {
        val tvStudentName: TextView = view.findViewById(R.id.tvStudentName)
        val tvStudentMobile: TextView = view.findViewById(R.id.tvStudentMobile)
        val tvStudentPaid: TextView = view.findViewById(R.id.tvStudentPaid)
        val tvStudentDebt: TextView = view.findViewById(R.id.tvStudentDebt)
        val tvStudentStatus: TextView = view.findViewById(R.id.tvStudentStatus)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): StudentViewHolder {
        val view = LayoutInflater.from(parent.context)
            .inflate(R.layout.item_class_student, parent, false)
        return StudentViewHolder(view)
    }

    override fun onBindViewHolder(holder: StudentViewHolder, position: Int) {
        val student = students[position]

        // Try to get full student data if available
        val activity = holder.itemView.context as? ClassDetailActivity
        val fullStudent = activity?.studentsFullData?.students?.find { it.enrollment_id == student.enrollment_id }

        if (fullStudent != null) {
            val dType = fullStudent.discount_type ?: "none"
            val dVal = fullStudent.discount_value ?: 0
            val codeStr = if (fullStudent.student_code != null) holder.itemView.context.getString(R.string.cdetail_code_row, fullStudent.student_code) else ""

            if (dType != "none" && dVal > 0) {
                val dValDisp = if (dType == "percentage") "$dVal%" else holder.itemView.context.getString(R.string.common_toman_format, dVal)
                holder.tvStudentName.text = holder.itemView.context.getString(R.string.cdetail_student_row, student.student_name, codeStr, dValDisp)
            } else {
                holder.tvStudentName.text = "${student.student_name}$codeStr"
            }

            // Show attendance information
            holder.tvStudentMobile.text = holder.itemView.context.getString(R.string.common_mobile_row, fullStudent.mobile)

            // Show attendance rate
            // درصد + شمارش واقعی همین کلاس: «۰٪» یعنی غایب بوده یا هنوز جلسه‌ای نبوده؛ عدد خام این را نمی‌گفت.
            holder.tvStudentPaid.text = holder.itemView.context.getString(R.string.cdetail_att_pct, String.format("%.1f", fullStudent.attendance_rate)) +
                "\n" + holder.itemView.context.getString(
                    R.string.cdetail_att_counts, fullStudent.present_count, fullStudent.absent_count, fullStudent.total_sessions
                )
            holder.tvStudentPaid.visibility = View.VISIBLE

            // فقط دو سهم همین enrollment را نشان بده؛ «بدهی کل» عمداً حذف شده است.
            val hasDebt = fullStudent.debt_teacher > 0 || fullStudent.debt_institute > 0
            if (hasDebt) {
                val debtText = holder.itemView.context.getString(
                    R.string.cdetail_debt_split,
                    String.format("%,d", fullStudent.debt_teacher),
                    String.format("%,d", fullStudent.debt_institute)
                )
                val unpaidSessions = fullStudent.unpaid_sessions ?: 0
                holder.tvStudentDebt.text = if (unpaidSessions > 0)
                    debtText + holder.itemView.context.getString(R.string.cdetail_debt_sessions, unpaidSessions.toString())
                else debtText
                holder.tvStudentStatus.text = holder.itemView.context.getString(R.string.cdetail_unsettled)
                holder.tvStudentStatus.setTextColor(UiColors.resolve(holder.itemView.context, R.color.status_danger)) // Red
            } else {
                holder.tvStudentDebt.text = holder.itemView.context.getString(
                    R.string.cdetail_debt_split, "0", "0"
                )
                holder.tvStudentStatus.text = holder.itemView.context.getString(R.string.cdetail_settled)
                holder.tvStudentStatus.setTextColor(UiColors.resolve(holder.itemView.context, R.color.status_success)) // Green
            }

            // Show suspension status if applicable
            if (fullStudent.is_suspended) {
                holder.tvStudentStatus.text = holder.itemView.context.getString(R.string.cdetail_susp)
                holder.tvStudentStatus.setTextColor(UiColors.resolve(holder.itemView.context, R.color.status_warning)) // Orange
            }
        } else {
            // Fallback to basic info
            holder.tvStudentMobile.text = holder.itemView.context.getString(R.string.cdetail_sid_row, student.student_id)

            // Fallback هم باید همان دو سهم را نشان دهد، نه بدهی کل.
            val hasDebt = student.debt_teacher > 0 || student.debt_institute > 0
            holder.tvStudentDebt.text = holder.itemView.context.getString(
                R.string.cdetail_debt_split,
                String.format("%,d", student.debt_teacher),
                String.format("%,d", student.debt_institute)
            )
            holder.tvStudentStatus.text = holder.itemView.context.getString(
                if (hasDebt) R.string.cdetail_unsettled else R.string.cdetail_settled
            )
            holder.tvStudentStatus.setTextColor(
                UiColors.resolve(
                    holder.itemView.context,
                    if (hasDebt) R.color.status_danger else R.color.status_success
                )
            )

            // Hide paid info
            holder.tvStudentPaid.visibility = View.GONE
        }

        // Make the whole item clickable
        holder.itemView.setOnClickListener {
            onStudentClick(student.student_id, student.student_name)
        }

        // Make student name specifically clickable
        holder.tvStudentName.setOnClickListener {
            onStudentClick(student.student_id, student.student_name)
        }
    }

    override fun getItemCount() = students.size
}
