package com.example.kharazmiadmin

import android.graphics.Color
import android.os.Bundle
import android.text.Editable
import android.text.TextWatcher
import android.view.View
import android.view.animation.AnimationUtils
import android.widget.ArrayAdapter
import android.widget.AutoCompleteTextView
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import android.widget.ViewFlipper
import android.widget.CheckBox
import androidx.lifecycle.lifecycleScope
import com.google.android.material.progressindicator.LinearProgressIndicator
import com.google.android.material.textfield.TextInputEditText
import ir.hamsaa.persiandatepicker.PersianDatePickerDialog
import ir.hamsaa.persiandatepicker.util.PersianCalendar
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import retrofit2.http.Body
import retrofit2.http.POST
import retrofit2.http.GET
import retrofit2.HttpException
import java.util.Locale

// ==========================================
// API Interfaces
// ==========================================
interface RegisterApi {
    @POST("students/register_and_enroll")
    suspend fun registerAndEnrollStudent(@Body data: StudentRegisterAndEnrollRequest): RegisterResponse

    @GET("classes/list")
    suspend fun getClassesList(): List<ClassListItem>
}

class StudentRegisterActivity : BaseActivity() {

    // --- UI Components ---
    private lateinit var viewFlipper: ViewFlipper
    private lateinit var btnNext: Button
    private lateinit var btnPrevious: Button
    private lateinit var stepProgress: LinearProgressIndicator

    // --- Step 1: Inputs ---
    private lateinit var etFirstName: TextInputEditText
    private lateinit var etLastName: TextInputEditText
    private lateinit var etNationalCode: TextInputEditText
    private lateinit var etFatherName: TextInputEditText
    private lateinit var etBirthDate: TextInputEditText
    private lateinit var acGender: AutoCompleteTextView
    private lateinit var acStudyStatus: AutoCompleteTextView
    private lateinit var etStudentMobile: TextInputEditText
    private lateinit var etParentMobile: TextInputEditText

    // --- ثبت‌نام مستقیم در کلاس (جدید) ---
    private lateinit var acChooseClass: AutoCompleteTextView
    private lateinit var llDirectEnrollFields: LinearLayout
    private lateinit var etRegBaseTuition: TextInputEditText
    private lateinit var acRegDiscountType: AutoCompleteTextView
    private lateinit var etRegDiscountValue: TextInputEditText
    private lateinit var tvRegFinalTuitionPreview: TextView

    // --- Step 2: Review Views (نمایش اطلاعات جهت تایید) ---
    private lateinit var tvReviewName: TextView
    private lateinit var tvReviewFather: TextView
    private lateinit var tvReviewCode: TextView
    private lateinit var tvReviewGender: TextView
    private lateinit var tvReviewStudyStatus: TextView
    private lateinit var tvReviewBirth: TextView
    private lateinit var tvReviewMobile: TextView
    private lateinit var tvReviewParent: TextView
    private lateinit var tvReviewDirectEnrollClass: TextView

    // متغیرهای انتخابی کلاس
    private var activeClasses: List<ClassListItem> = emptyList()
    private var selectedClassId: Int? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_student_register)

        initViews()
        setupDropdowns()
        setupDatePicker()
        fetchClassesFromServer()

        // --- Navigation Logic ---
        btnNext.setOnClickListener {
            val currentStep = viewFlipper.displayedChild
            if (currentStep == 0) {
                // اگر در مرحله اول هستیم: اعتبارسنجی -> نمایش مرور -> رفتن به مرحله بعد
                if (validateInputs()) {
                    populateReviewPage() // 👈 پر کردن صفحه تایید
                    viewFlipper.inAnimation = AnimationUtils.loadAnimation(this, R.anim.slide_in_right)
                    viewFlipper.outAnimation = AnimationUtils.loadAnimation(this, R.anim.slide_out_left)
                    viewFlipper.showNext()
                    updateUiState(1)
                }
            } else {
                // اگر در مرحله دوم هستیم: ثبت نهایی ترکیبی تراکنشی
                registerStudentAndEnrollDirectly()
            }
        }

        btnPrevious.setOnClickListener {
            viewFlipper.inAnimation = AnimationUtils.loadAnimation(this, android.R.anim.slide_in_left)
            viewFlipper.outAnimation = AnimationUtils.loadAnimation(this, android.R.anim.slide_out_right)
            viewFlipper.showPrevious()
            updateUiState(0)
        }
    }

    private fun initViews() {
        viewFlipper = findViewById(R.id.viewFlipper)
        btnNext = findViewById(R.id.btnNext)
        btnPrevious = findViewById(R.id.btnPrevious)
        stepProgress = findViewById(R.id.stepProgress)

        // Inputs
        etFirstName = findViewById(R.id.etFirstName)
        etLastName = findViewById(R.id.etLastName)
        etNationalCode = findViewById(R.id.etNationalCode)
        etFatherName = findViewById(R.id.etFatherName)
        etBirthDate = findViewById(R.id.etBirthDate)
        acGender = findViewById(R.id.acGender)
        acStudyStatus = findViewById(R.id.acStudyStatus)
        etStudentMobile = findViewById(R.id.etStudentMobile)
        etParentMobile = findViewById(R.id.etParentMobile)

        // ثبت‌نام مستقیم در کلاس
        acChooseClass = findViewById(R.id.acChooseClass)
        llDirectEnrollFields = findViewById(R.id.llDirectEnrollFields)
        etRegBaseTuition = findViewById(R.id.etRegBaseTuition)
        acRegDiscountType = findViewById(R.id.acRegDiscountType)
        etRegDiscountValue = findViewById(R.id.etRegDiscountValue)
        tvRegFinalTuitionPreview = findViewById(R.id.tvRegFinalTuitionPreview)

        // Review TextViews
        tvReviewName = findViewById(R.id.tvReviewName)
        tvReviewFather = findViewById(R.id.tvReviewFather)
        tvReviewCode = findViewById(R.id.tvReviewCode)
        tvReviewGender = findViewById(R.id.tvReviewGender)
        tvReviewStudyStatus = findViewById(R.id.tvReviewStudyStatus)
        tvReviewBirth = findViewById(R.id.tvReviewBirth)
        tvReviewMobile = findViewById(R.id.tvReviewMobile)
        tvReviewParent = findViewById(R.id.tvReviewParent)
        tvReviewDirectEnrollClass = findViewById(R.id.tvReviewDirectEnrollClass)
    }

    private fun setupDropdowns() {
        val genderAdapter = ArrayAdapter(this, android.R.layout.simple_dropdown_item_1line, arrayOf("آقا", "خانم"))
        acGender.setAdapter(genderAdapter)
        acGender.setText("آقا", false) // مقدار پیش‌فرض

        val studyStatusAdapter = ArrayAdapter(
            this, 
            android.R.layout.simple_dropdown_item_1line, 
            arrayOf("در حال تحصیل", "فارغ‌التحصیل", "انصرافی", "سایر")
        )
        acStudyStatus.setAdapter(studyStatusAdapter)
        acStudyStatus.setText("در حال تحصیل", false) // مقدار پیش‌فرض

        // نوع تخفیف ثبت‌نام مستقیم
        val discountAdapter = ArrayAdapter(this, android.R.layout.simple_dropdown_item_1line, arrayOf("بدون تخفیف", "درصدی", "مبلغ ثابت"))
        acRegDiscountType.setAdapter(discountAdapter)
        acRegDiscountType.setText("بدون تخفیف", false)

        // فرمول پیش‌نمایش آنی نهایی شهریه ثبت نام مستقیم
        val updatePreview = {
            val baseTuition = etRegBaseTuition.text.toString().toIntOrNull() ?: 0
            val dType = when (acRegDiscountType.text.toString()) {
                "درصدی" -> "percentage"
                "مبلغ ثابت" -> "fixed"
                else -> "none"
            }
            val dVal = etRegDiscountValue.text.toString().toIntOrNull() ?: 0

            val discountAmt = when (dType) {
                "percentage" -> (baseTuition * dVal) / 100
                "fixed" -> dVal
                else -> 0
            }
            val finalTuition = Math.max(0, baseTuition - discountAmt)
            tvRegFinalTuitionPreview.text = getString(R.string.sreg_tuition_preview, String.format(Locale("en", "US"), "%,d", finalTuition))
        }

        etRegBaseTuition.addTextChangedListener(object : TextWatcher {
            override fun afterTextChanged(s: Editable?) { updatePreview() }
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {}
        })

        etRegDiscountValue.addTextChangedListener(object : TextWatcher {
            override fun afterTextChanged(s: Editable?) { updatePreview() }
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {}
        })

        acRegDiscountType.setOnItemClickListener { _, _, _, _ ->
            updatePreview()
        }
    }

    private fun setupDatePicker() {
        etBirthDate.showSoftInputOnFocus = false
        etBirthDate.setOnClickListener {
            val picker = PersianDatePickerDialog(this)
                .setPositiveButtonString(getString(R.string.common_ok))
                .setNegativeButton(getString(R.string.common_cancel))
                .setTodayButton(getString(R.string.common_today))
                .setTodayButtonVisible(true)
                .setMinYear(1300)
                .setMaxYear(PersianCalendar().persianYear)
                .setInitDate(1385, 1, 1)
                .setActionTextColor(UiColors.resolve(this@StudentRegisterActivity, R.color.ds_accent))
                // Keep the picker surface and NumberPicker columns on the active day/night palette.
                .setBackgroundColor(UiColors.resolve(this@StudentRegisterActivity, R.color.ds_bg_surface))
                .setPickerBackgroundColor(UiColors.resolve(this@StudentRegisterActivity, R.color.ds_bg_surface_2))
                .setTitleColor(UiColors.resolve(this@StudentRegisterActivity, R.color.ds_text_primary))
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
    }

    private fun fetchClassesFromServer() {
        val retrofit = RetrofitClient.getInstance(this)
        val api = retrofit.create(RegisterApi::class.java)

        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.

        lifecycleScope.launch(Dispatchers.IO) {
            try {
                // دریافت لیست کلاس‌های فعال و پر کردن اسپینر کلاس
                activeClasses = api.getClassesList().filter { !it.is_suspended }
                val choices = ArrayList<String>()
                choices.add(getString(R.string.sreg_no_class))
                activeClasses.forEach { choices.add("${it.title} (${it.code})") }

                withContext(Dispatchers.Main) {
                    val classAdapter = ArrayAdapter(this@StudentRegisterActivity, android.R.layout.simple_dropdown_item_1line, choices)
                    acChooseClass.setAdapter(classAdapter)
                    acChooseClass.setText(getString(R.string.sreg_no_class), false)

                    acChooseClass.setOnItemClickListener { parent, _, position, _ ->
                        if (position == 0) {
                            selectedClassId = null
                            llDirectEnrollFields.visibility = View.GONE
                        } else {
                            val selectedClass = activeClasses[position - 1]
                            selectedClassId = selectedClass.id
                            llDirectEnrollFields.visibility = View.VISIBLE
                        }
                    }
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                android.util.Log.e("StudentRegisterActivity", "fetchClassesFromServer failed", e)
            }
        }
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

    // بررسی پر بودن فیلدها و فرمت‌های ورودی
    private fun validateInputs(): Boolean {
        var isValid = true
        
        val firstName = etFirstName.text.toString().trim()
        val lastName = etLastName.text.toString().trim()
        val nationalCode = etNationalCode.text.toString().trim()
        val studentMobile = etStudentMobile.text.toString().trim()
        val parentMobile = etParentMobile.text.toString().trim()

        if (firstName.isEmpty()) { etFirstName.error = getString(R.string.sreg_required); isValid = false }
        if (lastName.isEmpty()) { etLastName.error = getString(R.string.sreg_required); isValid = false }
        
        if (nationalCode.isEmpty()) { 
            etNationalCode.error = getString(R.string.sreg_required)
            isValid = false 
        } else if (!isValidNationalCode(nationalCode)) {
            etNationalCode.error = getString(R.string.sreg_national_bad)
            isValid = false
        }
        
        if (studentMobile.isEmpty()) { 
            etStudentMobile.error = getString(R.string.sreg_required)
            isValid = false 
        } else if (studentMobile.length !in 10..11 || !studentMobile.all { it.isDigit() }) {
            etStudentMobile.error = getString(R.string.sreg_digits)
            isValid = false
        }

        if (parentMobile.isNotEmpty() && (parentMobile.length !in 10..11 || !parentMobile.all { it.isDigit() })) {
            etParentMobile.error = getString(R.string.sreg_digits)
            isValid = false
        }

        // بررسی ولیدیشن فیلدهای ثبت‌نام مستقیم کلاس
        if (selectedClassId != null) {
            val baseTuition = etRegBaseTuition.text.toString().toIntOrNull() ?: 0
            val dType = when (acRegDiscountType.text.toString()) {
                "درصدی" -> "percentage"
                "مبلغ ثابت" -> "fixed"
                else -> "none"
            }
            val dVal = etRegDiscountValue.text.toString().toIntOrNull() ?: 0

            if (baseTuition < 0) {
                etRegBaseTuition.error = getString(R.string.sreg_tuition_neg)
                isValid = false
            }
            if (dType == "percentage" && (dVal < 0 || dVal > 100)) {
                etRegDiscountValue.error = getString(R.string.sreg_disc_range)
                isValid = false
            }
            if (dType == "fixed" && (dVal < 0 || dVal > baseTuition)) {
                etRegDiscountValue.error = getString(R.string.sreg_disc_over)
                isValid = false
            }
        }

        if (!isValid) Toast.makeText(this, getString(R.string.sreg_fix_errors), Toast.LENGTH_SHORT).show()
        return isValid
    }

    // 🔥 انتقال اطلاعات از فرم به صفحه تاییدیه
    private fun populateReviewPage() {
        tvReviewName.text = getString(R.string.sreg_rev_name, etFirstName.text, etLastName.text)
        tvReviewFather.text = getString(R.string.sreg_rev_father, etFatherName.text)
        tvReviewCode.text = getString(R.string.sreg_rev_code, etNationalCode.text)
        tvReviewGender.text = getString(R.string.sreg_rev_gender, acGender.text)
        tvReviewStudyStatus.text = getString(R.string.sreg_rev_study, acStudyStatus.text)
        tvReviewBirth.text = getString(R.string.sreg_rev_birth, etBirthDate.text)
        tvReviewMobile.text = getString(R.string.sreg_rev_mobile, etStudentMobile.text)
        tvReviewParent.text = getString(R.string.sreg_rev_parent, etParentMobile.text)
        tvReviewDirectEnrollClass.text = getString(R.string.sreg_rev_class, acChooseClass.text)
    }

    // تغییر وضعیت دکمه‌ها و پروگرس بار
    private fun updateUiState(step: Int) {
        if (step == 0) { // فرم ورودی
            btnPrevious.visibility = View.INVISIBLE
            btnNext.text = getString(R.string.common_next)
            stepProgress.setProgress(50, true)
        } else { // تایید نهایی
            btnPrevious.visibility = View.VISIBLE
            btnNext.text = getString(R.string.sreg_confirm)
            stepProgress.setProgress(100, true)
        }
    }

    // فرستادن اطلاعات ثبت‌نام ترکیبی به سرور به صورت تراکنشی
    private fun registrationError(error: Exception): String {
        if (error is HttpException) {
            val body = error.response()?.errorBody()?.string().orEmpty()
            val detail = try {
                val value = org.json.JSONObject(body).opt("detail")
                when (value) {
                    is String -> value
                    null -> ""
                    else -> value.toString()
                }
            } catch (_: Exception) { "" }
            return if (detail.isNotBlank()) "ثبت نام ناموفق (HTTP ${error.code()}): $detail"
            else "ثبت نام ناموفق (HTTP ${error.code()})"
        }
        return "ثبت نام ناموفق: ${error.message ?: "خطای شبکه"}"
    }

    private fun registerStudentAndEnrollDirectly() {
        val baseTuition = etRegBaseTuition.text.toString().toIntOrNull() ?: 0
        val dType = when (acRegDiscountType.text.toString()) {
            "درصدی" -> "percentage"
            "مبلغ ثابت" -> "fixed"
            else -> "none"
        }
        val dVal = etRegDiscountValue.text.toString().toIntOrNull() ?: 0
        val cbRegSplitInstallments = findViewById<CheckBox>(R.id.cbRegSplitInstallments)

        // محاسبات اقساط در صورت تیک خوردن
        var installmentList: List<InstallmentCreate>? = null
        if (selectedClassId != null && cbRegSplitInstallments.isChecked) {
            val discountAmt = when (dType) {
                "percentage" -> (baseTuition * dVal) / 100
                "fixed" -> dVal
                else -> 0
            }
            val finalTuition = Math.max(0, baseTuition - discountAmt)
            // شهریهٔ صفر قسط ندارد؛ ارسال دو قسط صفر از سمت Gson باعث 422
            // در InstallmentCreate (مبلغ باید مثبت باشد) و خطای ظاهراً مربوط به شهریه می‌شد.
            if (finalTuition > 0) {
                // FIX: برای مبلغ ۱ هم هیچ قسط صفر ارسال نشود.
                val todayDate = JalaliUtils.todayJalaliString()
                val futureDate = JalaliUtils.jalaliStringDaysFromNow(30)
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

        val data = StudentRegisterAndEnrollRequest(
            first_name = etFirstName.text.toString().trim(),
            last_name = etLastName.text.toString().trim(),
            father_name = etFatherName.text.toString().trim(),
            national_code = etNationalCode.text.toString().trim(),
            birth_date = etBirthDate.text.toString().trim(),
            student_mobile = etStudentMobile.text.toString().trim(),
            parent_mobile = etParentMobile.text.toString().trim(),
            home_phone = "",
            address = "ثبت نشده",
            study_status = acStudyStatus.text.toString().trim(),
            gender = acGender.text.toString().trim(),
            
            // اطلاعات انتخابی کلاس
            course_id = selectedClassId,
            total_tuition = baseTuition,
            paid_amount = 0,
            payment_method = "-",
            receiver = "-",
            discount_type = dType,
            discount_value = dVal,
            installments = installmentList
        )

        // FIX: Display the real GoldButton spinner; keep the legacy fallback for other button types.
        (btnNext as? GoldButton)?.setLoading(true) ?: run {
            btnNext.isEnabled = false
            btnNext.text = getString(R.string.common_sending)
        }

        val retrofit = RetrofitClient.getInstance(this)
        val api = retrofit.create(RegisterApi::class.java)

        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.

        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val response = api.registerAndEnrollStudent(data)
                withContext(Dispatchers.Main) {
                    // FIX: Restore the button on both success and failure.
                    (btnNext as? GoldButton)?.setLoading(false)
                    Toast.makeText(this@StudentRegisterActivity, getString(R.string.common_ok_msg, response.message), Toast.LENGTH_LONG).show()
                    
                    // ابطال هوشمند کش لیست دانش‌آموزان ادمین
                    CacheManager.clearByPrefix(this@StudentRegisterActivity, "person_list_STUDENT")
                    
                    // در صورت ثبت‌نام در کلاس، کش آن کلاس نیز باطل شود
                    if (selectedClassId != null) {
                        CacheManager.clear(this@StudentRegisterActivity, "class_report_${selectedClassId}")
                        CacheManager.clear(this@StudentRegisterActivity, "class_students_full_${selectedClassId}")
                    }
                    
                    finish()
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    // FIX: Restore the button on both success and failure.
                    (btnNext as? GoldButton)?.setLoading(false)
                    Toast.makeText(this@StudentRegisterActivity, registrationError(e), Toast.LENGTH_LONG).show()
                    android.util.Log.e("StudentRegisterActivity", "registerStudentAndEnrollDirectly failed", e)
                    btnNext.isEnabled = true
                    btnNext.text = getString(R.string.btn_retry)
                }
            }
        }
    }
}
