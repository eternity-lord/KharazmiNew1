package com.example.kharazmiadmin

import android.app.AlertDialog
import android.content.Context
import android.content.Intent
import android.graphics.Color
import android.net.Uri
import android.os.Bundle
import android.print.PrintAttributes
import android.print.PrintManager
import android.view.View
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.lifecycle.lifecycleScope
import com.google.android.material.textfield.TextInputEditText
import ir.hamsaa.persiandatepicker.PersianDatePickerDialog
import ir.hamsaa.persiandatepicker.util.PersianCalendar
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.util.Locale

class EditStudentActivity : BaseActivity() {

    private var studentId: Int = -1
    private var currentVersion: Int = 1
    
    // فیلدهای ورودی
    private lateinit var etFirstName: TextInputEditText
    private lateinit var etLastName: TextInputEditText
    private lateinit var etFatherName: TextInputEditText
    private lateinit var etNationalCode: TextInputEditText
    private lateinit var etBirthDate: TextInputEditText
    private lateinit var etStudentMobile: TextInputEditText
    private lateinit var etParentMobile: TextInputEditText

    // دکمه‌ها و بخش‌های نمایشی مالی
    private lateinit var btnDialMobile1: ImageView
    private lateinit var btnDialMobile2: ImageView
    private lateinit var tvOverallPaidInstitute: TextView
    private lateinit var tvOverallDebtInstitute: TextView
    private lateinit var llTeachersFinancialContainer: LinearLayout
    private lateinit var btnSave: Button
    private lateinit var btnCancel: Button

    private var userSubRole: String = ""
    private var previousPaidInstitute: Long? = null
    private var previousDebtInstitute: Long? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_edit_student)

        studentId = intent.getIntExtra("STUDENT_ID", -1)
        if (studentId == -1) {
            Toast.makeText(this, getString(R.string.estudent_sid_error), Toast.LENGTH_SHORT).show()
            finish()
            return
        }

        // بررسی نقش جهت مجاز بودن به تغییر کد ملی
        val credsPrefs = getSharedPreferences("UserCreds", Context.MODE_PRIVATE)
        userSubRole = credsPrefs.getString("USER_SUB_ROLE", "admin") ?: "admin"

        initViews()
        fetchCurrentData()

        // کلیک روی فیلد تاریخ تولد جهت انتخابگر خورشیدی
        etBirthDate.setOnClickListener {
            val picker = PersianDatePickerDialog(this)
                .setPositiveButtonString(getString(R.string.common_ok))
                .setNegativeButton(getString(R.string.common_cancel))
                .setTodayButton(getString(R.string.common_today))
                .setTodayButtonVisible(true)
                .setMinYear(1300)
                .setMaxYear(PersianCalendar().persianYear)
                .setInitDate(1385, 1, 1)
                .setActionTextColor(UiColors.resolve(this@EditStudentActivity, R.color.ds_accent))
                // Persian-Date-Picker-Dialog uses white backgrounds unless explicitly themed.
                .setBackgroundColor(UiColors.resolve(this@EditStudentActivity, R.color.ds_bg_surface))
                .setPickerBackgroundColor(UiColors.resolve(this@EditStudentActivity, R.color.ds_bg_surface_2))
                .setTitleColor(UiColors.resolve(this@EditStudentActivity, R.color.ds_text_primary))
                .setTitleType(PersianDatePickerDialog.WEEKDAY_DAY_MONTH_YEAR)
                .setShowInBottomSheet(true)
                .setListener(object : ir.hamsaa.persiandatepicker.Listener {
                    override fun onDateSelected(persianCalendar: PersianCalendar?) {
                        if (persianCalendar != null) {
                            val date = "${persianCalendar.persianYear}/${String.format("%02d", persianCalendar.persianMonth)}/${String.format("%02d", persianCalendar.persianDay)}"
                            etBirthDate.setText(date)
                        }
                    }
                    override fun onDismissed() {}
                })
            picker.show()
        }

        // کلیک شماره‌گیرها جهت تماس مستقیم تلفنی
        btnDialMobile1.setOnClickListener { makeCall(etStudentMobile.text.toString().trim()) }
        btnDialMobile2.setOnClickListener { makeCall(etParentMobile.text.toString().trim()) }

        // کلیک ذخیره
        btnSave.setOnClickListener {
            confirmAndSaveChanges()
        }

        // کلیک لغو عملیات
        btnCancel.setOnClickListener {
            confirmCancelOperation()
        }
    }

    private fun initViews() {
        etFirstName = findViewById(R.id.etEditFirstName)
        etLastName = findViewById(R.id.etEditLastName)
        etFatherName = findViewById(R.id.etEditFatherName)
        etNationalCode = findViewById(R.id.etEditNationalCode)
        etBirthDate = findViewById(R.id.etEditBirthDate)
        etStudentMobile = findViewById(R.id.etEditStudentMobile)
        etParentMobile = findViewById(R.id.etEditParentMobile)

        btnDialMobile1 = findViewById(R.id.btnDialMobile1)
        btnDialMobile2 = findViewById(R.id.btnDialMobile2)
        tvOverallPaidInstitute = findViewById(R.id.tvOverallPaidInstitute)
        tvOverallDebtInstitute = findViewById(R.id.tvOverallDebtInstitute)
        llTeachersFinancialContainer = findViewById(R.id.llTeachersFinancialContainer)
        
        btnSave = findViewById(R.id.btnSaveParams)
        btnCancel = findViewById(R.id.btnCancelEdit)
        
        ButtonAnimator.applyPillScaleAnimation(btnSave)
        ButtonAnimator.applyPillScaleAnimation(btnCancel)

        // غیرفعال کردن فیلد کد ملی در صورتی که کاربر جاری ادمین ارشد نباشد
        if (userSubRole == "admin") {
            etNationalCode.isEnabled = true
        } else {
            etNationalCode.isEnabled = false
            etNationalCode.alpha = 0.6f
        }
    }

    private fun fetchCurrentData() {
        val retrofit = RetrofitClient.getInstance(this)
        val api = retrofit.create(ProfileApi::class.java)

        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.

        lifecycleScope.launch(Dispatchers.IO) {
            try {
                // ۱. خواندن اطلاعات خام ویرایشی دانش‌آموز
                val profile = api.getStudentProfile(studentId)
                
                // ۲. خواندن اطلاعات مالی و کلاس‌های او
                val fullProfile = api.getFullStudentProfile(studentId)

                withContext(Dispatchers.Main) {
                    currentVersion = profile.version
                    etFirstName.setText(profile.first_name)
                    etLastName.setText(profile.last_name)
                    etFatherName.setText(profile.father_name ?: "")
                    etNationalCode.setText(profile.national_code)
                    etBirthDate.setText(profile.birth_date ?: "")
                    etStudentMobile.setText(profile.student_mobile)
                    etParentMobile.setText(profile.parent_mobile ?: "")

                    // مقداردهی مالی آموزشگاه به همراه کنترل هوشمند انیمیشن شمارنده چرخشی واقعی
                    val newPaid = fullProfile.total_paid_institute
                    val newDebt = fullProfile.debtInstitute

                    if (previousPaidInstitute == null || previousDebtInstitute == null) {
                        // لود اولیه صفحه: لود آنی عدد واقعی بدون انیمیشن چرخش از صفر
                        tvOverallPaidInstitute.text = String.format(Locale("en", "US"), getString(R.string.common_toman_format), newPaid)
                        tvOverallDebtInstitute.text = String.format(Locale("en", "US"), getString(R.string.common_toman_format), newDebt)
                    } else {
                        // رفرش پویای صفحه: انیمیشن چرخشی از مقدار واقعی قبلی به مقدار جدید واقعی
                        NumberAnimator.animateNumber(tvOverallPaidInstitute, previousPaidInstitute!!, newPaid)
                        NumberAnimator.animateNumber(tvOverallDebtInstitute, previousDebtInstitute!!, newDebt)
                    }

                    // ذخیره مقادیر جاری برای رفرش‌های بعدی
                    previousPaidInstitute = newPaid
                    previousDebtInstitute = newDebt

                    // مقداردهی مالی معلمان و مربیان کلاس‌ها به صورت پویا
                    llTeachersFinancialContainer.removeAllViews()
                    if (fullProfile.teachers_financial.isNullOrEmpty()) {
                        val tv = TextView(this@EditStudentActivity).apply {
                            text = getString(R.string.estudent_no_class)
                            gravity = android.view.Gravity.CENTER
                            setTextColor(UiColors.resolve(this@EditStudentActivity, R.color.text_secondary))
                            textSize = 12f
                            setPadding(0, 16, 0, 16)
                        }
                        llTeachersFinancialContainer.addView(tv)
                    } else {
                        fullProfile.teachers_financial.forEach { tf ->
                            val row = LinearLayout(this@EditStudentActivity).apply {
                                orientation = LinearLayout.VERTICAL
                                setPadding(0, 8, 0, 8)
                                val border = View(this@EditStudentActivity).apply {
                                    layoutParams = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 1).apply {
                                        setMargins(0, 4, 0, 8)
                                    }
                                    setBackgroundColor(UiColors.resolve(this@EditStudentActivity, R.color.ds_border))
                                }
                                addView(border)
                                
                                val tvTitle = TextView(this@EditStudentActivity).apply {
                                    text = if (tf.is_unassigned) {
                                        "بدهی بدون کلاس"
                                    } else {
                                        "بدهی کلاس ${tf.course_title} — معلم ${tf.teacher_name ?: "بدون معلم"}"
                                    }
                                    textStyleBold()
                                    setTextColor(UiColors.resolve(this@EditStudentActivity, R.color.text_primary))
                                    textSize = 13f
                                }
                                addView(tvTitle)

                                val hlPaid = LinearLayout(this@EditStudentActivity).apply {
                                    orientation = LinearLayout.HORIZONTAL
                                    val l = TextView(this@EditStudentActivity).apply { text = getString(R.string.estudent_paid_label); textSize = 12f; setTextColor(UiColors.resolve(this@EditStudentActivity, R.color.text_secondary)) }
                                    val v = TextView(this@EditStudentActivity).apply { text = getString(R.string.common_toman_format, tf.paid_teacher); textSize = 12f; setTextColor(UiColors.resolve(this@EditStudentActivity, R.color.status_success)); textStyleBold() }
                                    addView(l)
                                    addView(View(this@EditStudentActivity).apply { layoutParams = LinearLayout.LayoutParams(0, 1, 1f) })
                                    addView(v)
                                }
                                addView(hlPaid)

                                val hlDebt = LinearLayout(this@EditStudentActivity).apply {
                                    orientation = LinearLayout.HORIZONTAL
                                    val l = TextView(this@EditStudentActivity).apply { text = getString(R.string.estudent_debt_label); textSize = 12f; setTextColor(UiColors.resolve(this@EditStudentActivity, R.color.text_secondary)) }
                                    val v = TextView(this@EditStudentActivity).apply { text = getString(R.string.common_toman_format, tf.debt); textSize = 12f; setTextColor(UiColors.resolve(this@EditStudentActivity, R.color.status_danger)); textStyleBold() }
                                    addView(l)
                                    addView(View(this@EditStudentActivity).apply { layoutParams = LinearLayout.LayoutParams(0, 1, 1f) })
                                    addView(v)
                                }
                                addView(hlDebt)
                            }
                            llTeachersFinancialContainer.addView(row)
                        }
                    }
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@EditStudentActivity, getString(R.string.estudent_current_error), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun TextView.textStyleBold() {
        this.setTypeface(this.typeface, android.graphics.Typeface.BOLD)
    }

    private fun isValidNationalCode(code: String): Boolean {
        if (code.length != 10) return false
        if (!code.all { it.isDigit() }) return false
        if (code.toSet().size == 1) return false
        val digits = code.map { it.toString().toInt() }
        val sum = (0..8).sumOf { digits[it] * (10 - it) }
        val rem = sum % 11
        val control = digits[9]
        return if (rem < 2) {
            control == rem
        } else {
            control == (11 - rem)
        }
    }

    private fun confirmAndSaveChanges() {
        val firstName = etFirstName.text.toString().trim()
        val lastName = etLastName.text.toString().trim()
        val fatherName = etFatherName.text.toString().trim()
        val nationalCode = etNationalCode.text.toString().trim()
        val birthDate = etBirthDate.text.toString().trim()
        val studentMobile = etStudentMobile.text.toString().trim()
        val parentMobile = etParentMobile.text.toString().trim()

        if (firstName.isEmpty()) { etFirstName.error = getString(R.string.treg_name_req); return }
        if (lastName.isEmpty()) { etLastName.error = getString(R.string.treg_family_req); return }
        if (!isValidNationalCode(nationalCode)) { etNationalCode.error = getString(R.string.common_national_invalid); return }
        if (studentMobile.length !in 10..11 || !studentMobile.all { it.isDigit() }) {
            etStudentMobile.error = getString(R.string.estudent_mobile_bad)
            return
        }
        if (parentMobile.isNotEmpty() && (parentMobile.length !in 10..11 || !parentMobile.all { it.isDigit() })) {
            etParentMobile.error = getString(R.string.estudent_parent_mobile_bad)
            return
        }

        // دیالوگ تایید بله/خیر/لغو تغییرات
        AlertDialog.Builder(this)
            .setTitle(getString(R.string.estudent_save_title))
            .setMessage(getString(R.string.estudent_save_msg))
            .setNegativeButton(getString(R.string.common_no), null)
            .setNeutralButton(getString(R.string.common_cancel)) { _, _ ->
                confirmCancelOperation()
            }
            .setPositiveButton(getString(R.string.common_yes)) { _, _ ->
                saveDataToServer(firstName, lastName, fatherName, nationalCode, birthDate, studentMobile, parentMobile)
            }
            .show()
    }

    private fun saveDataToServer(
        firstName: String, lastName: String, fatherName: String,
        nationalCode: String, birthDate: String, studentMobile: String, parentMobile: String
    ) {
        val data = StudentUpdate(
            first_name = firstName,
            last_name = lastName,
            father_name = fatherName.takeIf { it.isNotEmpty() },
            national_code = nationalCode,
            birth_date = birthDate.takeIf { it.isNotEmpty() },
            student_mobile = studentMobile,
            parent_mobile = parentMobile.takeIf { it.isNotEmpty() },
            version = currentVersion
        )

        val retrofit = RetrofitClient.getInstance(this)
        val api = retrofit.create(ProfileApi::class.java)

        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.

        // FIX L9: ضد دابل‌کلیک — در هر دو مسیر برمی‌گردد (موفقیت دیالوگ نشان می‌دهد و می‌ماند).
        btnSave.isEnabled = false
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                api.updateStudent(studentId, data)
                withContext(Dispatchers.Main) {
                    // ابطال کش
                    CacheManager.clear(this@EditStudentActivity, "student_full_profile_$studentId")
                    CacheManager.clearByPrefix(this@EditStudentActivity, "person_list_STUDENT")
                    
                    btnSave.isEnabled = true
                    showSummaryDialog(firstName, lastName, fatherName, nationalCode, birthDate, studentMobile, parentMobile)
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@EditStudentActivity, getString(R.string.estudent_update_error), Toast.LENGTH_LONG).show()
                    btnSave.isEnabled = true
                }
            }
        }
    }

    private fun showSummaryDialog(
        firstName: String, lastName: String, fatherName: String,
        nationalCode: String, birthDate: String, studentMobile: String, parentMobile: String
    ) {
        val message = listOf(
            getString(R.string.estudent_sum_title),
            "",
            getString(R.string.estudent_sum_name, firstName, lastName),
            getString(R.string.estudent_sum_father, fatherName),
            getString(R.string.estudent_sum_national, nationalCode),
            getString(R.string.estudent_sum_birth, birthDate),
            getString(R.string.estudent_sum_mobile, studentMobile),
            getString(R.string.estudent_sum_parent, parentMobile)
        ).joinToString("\n")

        AlertDialog.Builder(this)
            .setTitle(getString(R.string.estudent_saved_title))
            .setMessage(message)
            .setCancelable(false)
            .setNeutralButton(getString(R.string.estudent_print_btn)) { _, _ ->
                printStudentProfilePdf()
                finish()
            }
            .setPositiveButton(getString(R.string.btn_dismiss)) { _, _ ->
                finish()
            }
            .show()
    }

    private fun printStudentProfilePdf() {
        Toast.makeText(this, getString(R.string.estudent_print_loading), Toast.LENGTH_SHORT).show()
        val webView = WebView(this)
        webView.webViewClient = object : WebViewClient() {
            override fun onPageFinished(view: WebView, url: String) {
                val printManager = getSystemService(Context.PRINT_SERVICE) as PrintManager
                val printAdapter = webView.createPrintDocumentAdapter("Kharazmi_New_Student_Profile")
                val jobName = getString(R.string.estudent_print_job)
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
        val url = "${baseUrl}reports/student_profile/print?student_id=$studentId"

        webView.loadUrl(url, headers)
    }

    private fun confirmCancelOperation() {
        AlertDialog.Builder(this)
            .setTitle(getString(R.string.estudent_cancel_title))
            .setMessage(getString(R.string.estudent_cancel_msg))
            .setNegativeButton(getString(R.string.common_no), null)
            .setPositiveButton(getString(R.string.common_yes)) { _, _ ->
                returnToDashboard()
            }
            .show()
    }

    private fun returnToDashboard() {
        val credsPrefs = getSharedPreferences("UserCreds", Context.MODE_PRIVATE)
        val userRole = credsPrefs.getString("USER_ROLE", "") ?: ""
        
        val intent = if (userRole == "teacher") {
            Intent(this, TeacherDashboardActivity::class.java)
        } else {
            Intent(this, MainActivity::class.java)
        }
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK)
        startActivity(intent)
        finish()
    }

    private fun makeCall(number: String) {
        if (number.length < 3) return
        try {
            val intent = Intent(Intent.ACTION_DIAL, Uri.parse("tel:$number"))
            startActivity(intent)
        } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
            Toast.makeText(this, getString(R.string.estudent_no_call), Toast.LENGTH_SHORT).show()
        }
    }
}
