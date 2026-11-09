package com.example.kharazmiadmin

import android.app.AlertDialog
import android.graphics.Color
import android.os.Bundle
import android.view.View
import android.view.animation.AnimationUtils
import android.widget.ArrayAdapter
import android.widget.AutoCompleteTextView
import android.widget.Button
import android.widget.Toast
import android.widget.ViewFlipper
import androidx.lifecycle.lifecycleScope
import com.google.android.material.textfield.TextInputEditText
import ir.hamsaa.persiandatepicker.PersianDatePickerDialog
import ir.hamsaa.persiandatepicker.util.PersianCalendar
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import retrofit2.http.Body
import retrofit2.http.POST

// ==========================================
// API Interface
// ==========================================
interface TeacherApi {
    @POST("teachers/register")
    suspend fun registerTeacher(@Body data: TeacherRegisterData): RegisterResponse
}

class TeacherRegisterActivity : BaseActivity() {

    // --- UI Components ---
    private lateinit var viewFlipper: ViewFlipper
    private lateinit var btnNext: Button
    private lateinit var btnPrevious: Button

    // --- Step 1: Identity Inputs ---
    private lateinit var etFirstName: TextInputEditText
    private lateinit var etLastName: TextInputEditText
    private lateinit var etFatherName: TextInputEditText
    private lateinit var etNationalCode: TextInputEditText
    private lateinit var etBirthDate: TextInputEditText
    private lateinit var acGender: AutoCompleteTextView

    // --- Step 2: Contact Inputs ---
    private lateinit var etMobile: TextInputEditText
    private lateinit var acMarital: AutoCompleteTextView

    // --- Step 3: Job & Financial Inputs ---
    private lateinit var acEmployment: AutoCompleteTextView
    private lateinit var etCardNumber: TextInputEditText

    private val TOTAL_STEPS = 3

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_teacher_register)

        initViews()
        setupDropdowns()
        updateNavigationButtons()

        // انتخاب تاریخ تولد
        etBirthDate.showSoftInputOnFocus = false
        etBirthDate.setOnClickListener {
            val picker = PersianDatePickerDialog(this)
                .setPositiveButtonString(getString(R.string.common_ok))
                .setNegativeButton(getString(R.string.common_cancel))
                .setTodayButton(getString(R.string.common_today))
                .setTodayButtonVisible(true)
                .setMinYear(1300)
                .setMaxYear(PersianCalendar().persianYear)
                .setInitDate(1365, 1, 1)
                .setActionTextColor(UiColors.resolve(this@TeacherRegisterActivity, R.color.ds_accent))
                // The library is light by default; these tokens keep Jalali numbers readable in dark mode.
                .setBackgroundColor(UiColors.resolve(this@TeacherRegisterActivity, R.color.ds_bg_surface))
                .setPickerBackgroundColor(UiColors.resolve(this@TeacherRegisterActivity, R.color.ds_bg_surface_2))
                .setTitleColor(UiColors.resolve(this@TeacherRegisterActivity, R.color.ds_text_primary))
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

        // منطق دکمه‌های ناوبری فرم چند مرحله‌ای
        btnNext.setOnClickListener {
            val currentStep = viewFlipper.displayedChild

            when (currentStep) {
                0 -> {
                    if (validateIdentity()) {
                        setSlideAnimation("NEXT")
                        viewFlipper.showNext()
                        updateNavigationButtons()
                    }
                }
                1 -> {
                    if (validateContactAndMisc()) {
                        setSlideAnimation("NEXT")
                        viewFlipper.showNext()
                        updateNavigationButtons()
                    }
                }
                2 -> {
                    if (validateJob()) {
                        showConfirmationDialog()
                    }
                }
            }
        }

        btnPrevious.setOnClickListener {
            if (viewFlipper.displayedChild > 0) {
                setSlideAnimation("PREV")
                viewFlipper.showPrevious()
                updateNavigationButtons()
            }
        }
    }

    private fun initViews() {
        viewFlipper = findViewById(R.id.viewFlipper)
        btnNext = findViewById(R.id.btnNext)
        btnPrevious = findViewById(R.id.btnPrevious)

        etFirstName = findViewById(R.id.etTFirstName)
        etLastName = findViewById(R.id.etTLastName)
        etFatherName = findViewById(R.id.etTFatherName)
        etNationalCode = findViewById(R.id.etTNationalCode)
        etBirthDate = findViewById(R.id.etTBirthDate)
        acGender = findViewById(R.id.acTGender)

        etMobile = findViewById(R.id.etTMobile)
        acMarital = findViewById(R.id.acTMarital)

        acEmployment = findViewById(R.id.acTEmployment)
        etCardNumber = findViewById(R.id.etTCardNumber)
    }

    private fun setupDropdowns() {
        val genders = arrayOf("آقا", "خانم")
        acGender.setAdapter(ArrayAdapter(this, android.R.layout.simple_dropdown_item_1line, genders))
        acGender.setText("آقا", false)

        val maritalStatus = arrayOf("مجرد", "متاهل", "مطلقه")
        acMarital.setAdapter(ArrayAdapter(this, android.R.layout.simple_dropdown_item_1line, maritalStatus))
        acMarital.setText("متاهل", false)

        val employmentTypes = arrayOf("رسمی", "پیمانی", "آزاد")
        acEmployment.setAdapter(ArrayAdapter(this, android.R.layout.simple_dropdown_item_1line, employmentTypes))
        acEmployment.setText("رسمی", false)
    }

    private fun updateNavigationButtons() {
        val current = viewFlipper.displayedChild
        if (current == 0) {
            btnPrevious.visibility = View.INVISIBLE
            btnPrevious.isEnabled = false
        } else {
            btnPrevious.visibility = View.VISIBLE
            btnPrevious.isEnabled = true
        }

        if (current == TOTAL_STEPS - 1) {
            btnNext.text = getString(R.string.treg_submit)
        } else {
            btnNext.text = getString(R.string.common_next)
        }
    }

    private fun setSlideAnimation(direction: String) {
        if (direction == "NEXT") {
            viewFlipper.inAnimation = AnimationUtils.loadAnimation(this, R.anim.slide_in_right)
            viewFlipper.outAnimation = AnimationUtils.loadAnimation(this, R.anim.slide_out_left)
        } else {
            viewFlipper.inAnimation = AnimationUtils.loadAnimation(this, android.R.anim.slide_in_left)
            viewFlipper.outAnimation = AnimationUtils.loadAnimation(this, android.R.anim.slide_out_right)
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

    private fun validateIdentity(): Boolean {
        var isValid = true
        if (etFirstName.text.isNullOrEmpty()) { etFirstName.error = getString(R.string.treg_name_req); isValid = false }
        if (etLastName.text.isNullOrEmpty()) { etLastName.error = getString(R.string.treg_family_req); isValid = false }
        
        val nc = etNationalCode.text.toString().trim()
        if (nc.isEmpty()) { 
            etNationalCode.error = getString(R.string.treg_national_req)
            isValid = false 
        } else if (!isValidNationalCode(nc)) {
            etNationalCode.error = getString(R.string.common_national_invalid)
            isValid = false
        }
        return isValid
    }

    private fun validateContactAndMisc(): Boolean {
        val mobile = etMobile.text.toString().trim()
        val marital = acMarital.text.toString().trim()
        val gender = acGender.text.toString().trim()

        if (mobile.isEmpty()) {
            Toast.makeText(this, getString(R.string.treg_mobile_req), Toast.LENGTH_SHORT).show()
            return false
        }
        if (mobile.length < 10) {
            Toast.makeText(this, getString(R.string.treg_mobile_bad), Toast.LENGTH_SHORT).show()
            return false
        }
        if (marital.isEmpty()) {
            Toast.makeText(this, getString(R.string.treg_marital_req), Toast.LENGTH_SHORT).show()
            return false
        }
        if (gender.isEmpty()) {
            Toast.makeText(this, getString(R.string.treg_gender_req), Toast.LENGTH_SHORT).show()
            return false
        }
        return true
    }

    private fun validateJob(): Boolean {
        if (etCardNumber.text.isNullOrEmpty()) {
            etCardNumber.error = getString(R.string.treg_card_req)
            return false
        }
        return true
    }

    private fun showConfirmationDialog() {
        val name = "${etFirstName.text} ${etLastName.text}"
        val father = etFatherName.text.toString()
        val nationalCode = etNationalCode.text.toString()
        val mobile = etMobile.text.toString()
        val marital = acMarital.text.toString()
        val gender = acGender.text.toString()
        val employment = acEmployment.text.toString()
        val card = etCardNumber.text.toString()

        val message = """
            ${getString(R.string.treg_rev_name, name)}
            ${getString(R.string.treg_rev_father, father)}
            ${getString(R.string.treg_rev_code, nationalCode)}
            ${getString(R.string.treg_rev_mobile, mobile)}
            ${getString(R.string.treg_rev_gender, gender)}
            ${getString(R.string.treg_rev_marital, marital)}
            ${getString(R.string.treg_rev_contract, employment)}
            ${getString(R.string.treg_rev_card, card)}
            
            ${getString(R.string.treg_rev_confirm)}
        """.trimIndent()

        AlertDialog.Builder(this)
            .setTitle(getString(R.string.treg_review_title))
            .setMessage(message)
            .setNegativeButton(getString(R.string.common_no), null)
            .setPositiveButton(getString(R.string.common_yes)) { _, _ ->
                submitTeacher()
            }
            .show()
    }

    private fun submitTeacher() {
        val nationalCodeStr = etNationalCode.text.toString().trim()
        val data = TeacherRegisterData(
            first_name = etFirstName.text.toString().trim(),
            last_name = etLastName.text.toString().trim(),
            father_name = etFatherName.text.toString().trim(),
            national_code = nationalCodeStr,
            birth_date = etBirthDate.text.toString().trim(),
            mobile = etMobile.text.toString().trim(),
            password = "hidden_auto_assigned", // به صورت مخفی در سرور ست می‌شود
            home_phone = "",
            card_number = etCardNumber.text.toString().trim(),
            marital_status = acMarital.text.toString(),
            gender = acGender.text.toString(),
            employment_type = acEmployment.text.toString(),
            profile_image = null // حذف فیلد عکس
        )

        // FIX: Display the real GoldButton spinner; keep the legacy fallback for other button types.
        (btnNext as? GoldButton)?.setLoading(true) ?: run {
            btnNext.isEnabled = false
            btnNext.text = getString(R.string.common_sending)
        }

        val retrofit = RetrofitClient.getInstance(this)
        val api = retrofit.create(TeacherApi::class.java)

        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.

        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val response = api.registerTeacher(data)
                withContext(Dispatchers.Main) {
                    // FIX: Restore the button on both success and failure.
                    (btnNext as? GoldButton)?.setLoading(false)
                    val assignedCode = response.teacher_code ?: "101" // پیش فرض ۱۰۱ در صورتی که نال باشد
                    // سرور جدید پسورد تصادفی یک‌بارمصرف برمی‌گرداند؛ فالبک به کد فقط برای سازگاری با سرور قدیمی
                    val initialPassword = response.initial_password ?: assignedCode.toString()

                    // ابطال کش لیست معلمان
                    CacheManager.clearByPrefix(this@TeacherRegisterActivity, "person_list_TEACHER")

                    val successMessage = """
                        ${getString(R.string.treg_ok_msg)}

                        ${getString(R.string.treg_sms_title)}
                        ${getString(R.string.treg_sms_user, nationalCodeStr)}
                        ${getString(R.string.treg_sms_pass, initialPassword)}
                        
                        ${getString(R.string.treg_warn_title)}
                        ${getString(R.string.treg_warn_msg)}
                    """.trimIndent()

                    AlertDialog.Builder(this@TeacherRegisterActivity)
                        .setTitle(getString(R.string.treg_success_title))
                        .setMessage(successMessage)
                        .setCancelable(false)
                        .setPositiveButton(getString(R.string.btn_dismiss)) { _, _ ->
                            finish()
                        }
                        .show()
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    // FIX: Restore the button on both success and failure.
                    (btnNext as? GoldButton)?.setLoading(false)
                    Toast.makeText(this@TeacherRegisterActivity, getString(R.string.common_submit_dup), Toast.LENGTH_LONG).show()
                    android.util.Log.e("TeacherRegisterActivity", "submitTeacher failed", e)
                    btnNext.isEnabled = true
                    btnNext.text = getString(R.string.treg_submit)
                }
            }
        }
    }
}
