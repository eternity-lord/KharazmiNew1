package com.example.kharazmiadmin

import android.os.Bundle
import android.widget.Button
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.lifecycle.lifecycleScope
import com.google.android.material.textfield.TextInputEditText
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class EditTeacherActivity : BaseActivity() {

    private var teacherId: Int = -1
    private var currentVersion: Int = 1
    private lateinit var etFirstName: TextInputEditText
    private lateinit var etLastName: TextInputEditText
    private lateinit var etFatherName: TextInputEditText
    private lateinit var etNationalCode: TextInputEditText
    private lateinit var etBirthDate: TextInputEditText
    private lateinit var etMobile: TextInputEditText
    private lateinit var etHomePhone: TextInputEditText
    private lateinit var etMaritalStatus: TextInputEditText
    private lateinit var etGender: TextInputEditText
    private lateinit var etEmploymentType: TextInputEditText
    private lateinit var etCardNumber: TextInputEditText
    private lateinit var btnSave: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_edit_teacher)

        teacherId = intent.getIntExtra("TEACHER_ID", -1)
        if (teacherId == -1) {
            Toast.makeText(this, getString(R.string.etchr_sid_error), Toast.LENGTH_SHORT).show()
            finish()
            return
        }

        initViews()
        fetchCurrentData()

        btnSave.setOnClickListener {
            saveChanges()
        }
    }

    private fun initViews() {
        etFirstName = findViewById(R.id.etEditTFirstName)
        etLastName = findViewById(R.id.etEditTLastName)
        etFatherName = findViewById(R.id.etEditTFatherName)
        etNationalCode = findViewById(R.id.etEditTNationalCode)
        etBirthDate = findViewById(R.id.etEditTBirthDate)
        etMobile = findViewById(R.id.etEditTMobile)
        etHomePhone = findViewById(R.id.etEditTHomePhone)
        etMaritalStatus = findViewById(R.id.etEditTMaritalStatus)
        etGender = findViewById(R.id.etEditTGender)
        etEmploymentType = findViewById(R.id.etEditTEmploymentType)
        etCardNumber = findViewById(R.id.etEditTCardNumber)
        btnSave = findViewById(R.id.btnSaveParams)
    }

    private fun fetchCurrentData() {
        val retrofit = RetrofitClient.getInstance(this)
        val api = retrofit.create(ProfileApi::class.java)

        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.

        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val profile = api.getTeacherProfile(teacherId)
                withContext(Dispatchers.Main) {
                    currentVersion = profile.version
                    // FIX(null-data): فیلدهای ناقص نباید null به ویوها بدهند (fallback = رشته‌ی خالی
                    // تا فرم ویرایش مربی باز شود؛ اعتبارسنجی سمت کلاینت مثل قبل باقی می‌ماند).
                    etFirstName.setText(profile.first_name ?: "")
                    etLastName.setText(profile.last_name ?: "")
                    etFatherName.setText(profile.father_name ?: "")
                    etNationalCode.setText(profile.national_code ?: "")
                    etBirthDate.setText(profile.birth_date ?: "")
                    etMobile.setText(profile.mobile ?: "")
                    etHomePhone.setText(profile.home_phone ?: "")
                    etMaritalStatus.setText(profile.marital_status ?: "")
                    etGender.setText(profile.gender ?: "")
                    etEmploymentType.setText(profile.employment_type ?: "")
                    etCardNumber.setText(profile.card_number ?: "")
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@EditTeacherActivity, getString(R.string.etchr_load_error), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun saveChanges() {
        val firstName = etFirstName.text.toString().trim()
        val lastName = etLastName.text.toString().trim()
        val fatherName = etFatherName.text.toString().trim()
        val nationalCode = etNationalCode.text.toString().trim()
        val birthDate = etBirthDate.text.toString().trim()
        val mobile = etMobile.text.toString().trim()
        val homePhone = etHomePhone.text.toString().trim()
        val maritalStatus = etMaritalStatus.text.toString().trim()
        val gender = etGender.text.toString().trim()
        val employmentType = etEmploymentType.text.toString().trim()
        val cardNumber = etCardNumber.text.toString().trim()

        // کلاینت ساید ولیدیشن
        if (firstName.isEmpty()) {
            Toast.makeText(this, getString(R.string.etchr_name_req), Toast.LENGTH_SHORT).show()
            return
        }
        if (lastName.isEmpty()) {
            Toast.makeText(this, getString(R.string.etchr_family_req), Toast.LENGTH_SHORT).show()
            return
        }
        // FIX: Bug 22 - require the national-code checksum, not just ten numeric characters.
        if (!InputValidation.isValidNationalCode(nationalCode)) {
            etNationalCode.error = getString(R.string.common_national_invalid)
            Toast.makeText(this, getString(R.string.common_national_invalid), Toast.LENGTH_SHORT).show()
            return
        }
        // FIX: Bug 22 - use the valid Kotlin range operator in this validation path.
        if (mobile.length !in 10..11 || !mobile.all { it.isDigit() }) {
            Toast.makeText(this, getString(R.string.etchr_mobile_bad), Toast.LENGTH_SHORT).show()
            return
        }
        if (cardNumber.isNotEmpty() && cardNumber.length != 16) {
            Toast.makeText(this, getString(R.string.etchr_card_bad), Toast.LENGTH_SHORT).show()
            return
        }

        val data = TeacherUpdate(
            first_name = firstName,
            last_name = lastName,
            father_name = fatherName.takeIf { it.isNotEmpty() },
            national_code = nationalCode,
            birth_date = birthDate.takeIf { it.isNotEmpty() },
            mobile = mobile,
            home_phone = homePhone.takeIf { it.isNotEmpty() },
            marital_status = maritalStatus.takeIf { it.isNotEmpty() },
            gender = gender.takeIf { it.isNotEmpty() },
            employment_type = employmentType.takeIf { it.isNotEmpty() },
            card_number = cardNumber.takeIf { it.isNotEmpty() },
            version = currentVersion
        )

        val retrofit = RetrofitClient.getInstance(this)
        val api = retrofit.create(ProfileApi::class.java)

        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.

        // FIX L9: ضد دابل‌کلیک — موفقیت finish می‌کند پس بازگشت فقط در خطا.
        btnSave.isEnabled = false
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val response = api.updateTeacher(teacherId, data)
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@EditTeacherActivity, getString(R.string.common_ok_msg, response.message), Toast.LENGTH_SHORT).show()
                    
                    // ابطال کش پروفایل و لیست معلمان
                    CacheManager.clear(this@EditTeacherActivity, "teacher_full_profile_$teacherId")
                    CacheManager.clearByPrefix(this@EditTeacherActivity, "person_list_TEACHER")
                    
                    finish()
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    btnSave.isEnabled = true
                    if (e is retrofit2.HttpException && e.code() == 409) {
                        AlertDialog.Builder(this@EditTeacherActivity)
                            .setTitle(getString(R.string.etchr_conflict_title))
                            .setMessage(getString(R.string.etchr_conflict_msg))
                            .setPositiveButton(getString(R.string.common_understood), null)
                            .show()
                    } else {
                        Toast.makeText(this@EditTeacherActivity, getString(R.string.etchr_edit_error), Toast.LENGTH_LONG).show()
                    }
                }
            }
        }
    }

    private infix fun Int.notIn(range: IntRange): Boolean {
        return this !in range
    }
}
