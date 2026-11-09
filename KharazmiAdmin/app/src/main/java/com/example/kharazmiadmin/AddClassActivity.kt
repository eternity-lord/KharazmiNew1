package com.example.kharazmiadmin

import android.content.Intent
import android.os.Bundle
import android.widget.ArrayAdapter
import android.widget.AutoCompleteTextView
import android.widget.Button
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.lifecycle.lifecycleScope
import com.google.android.material.textfield.TextInputEditText
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST

// API
interface AddClassApi {
    @GET("teachers/list")
    suspend fun getTeachers(): List<TeacherSimple>

    @POST("classes/create")
    suspend fun createClass(
        @Body data: ClassSubmitData,
        @retrofit2.http.Query("override") override: Boolean = false
    ): ClassResponse
}

class AddClassActivity : BaseActivity() {

    private var selectedTeacherId: Int = -1
    private var teachersList: List<TeacherSimple> = listOf()
    private var selectedColor: String = "#FFFFFF"

    // ✅ متغیر برای تشخیص اینکه آیا ادمین دارد کلاس می‌سازد یا معلم
    private var isAdminMode: Boolean = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_add_class)

        // ✅ دریافت وضعیت ادمین از صفحه قبل
        isAdminMode = intent.getBooleanExtra("IS_ADMIN_MODE", false)

        setupDropdowns()
        setupColorPicker()

        val autoTeacherId = intent.getIntExtra("AUTO_TEACHER_ID", -1)
        val autoTeacherName = intent.getStringExtra("AUTO_TEACHER_NAME")

        if (autoTeacherId != -1) {
            selectedTeacherId = autoTeacherId
            val acTeacher = findViewById<AutoCompleteTextView>(R.id.acTeacher)
            acTeacher.setText(autoTeacherName)
            acTeacher.isEnabled = false
        } else {
            fetchTeachers()
        }

        findViewById<Button>(R.id.btnSubmitClass).setOnClickListener {
            submitClass()
        }
    }

    private fun setupDropdowns() {
        val grades = arrayOf("اول ", "دوم ", "سوم ", "چهارم ", "پنجم ", "ششم ",
            "هفتم", "هشتم", "نهم",
            "دهم", "یازدهم", "دوازدهم",
            "کنکور", "فارغ‌التحصیل", "سایر")
        findViewById<AutoCompleteTextView>(R.id.acGrade).setAdapter(ArrayAdapter(this, android.R.layout.simple_dropdown_item_1line, grades))

        val eduTypes = arrayOf("تقویتی", "تیزهوشان", "کنکور", "المپیاد")
        findViewById<AutoCompleteTextView>(R.id.acEduType).setAdapter(ArrayAdapter(this, android.R.layout.simple_dropdown_item_1line, eduTypes))
    }

    private fun setupColorPicker() {
        val btnColor = findViewById<Button>(R.id.btnColorPicker)
        btnColor.setOnClickListener {
            val colors = arrayOf(getString(R.string.aclass_color_white), getString(R.string.aclass_color_green), getString(R.string.aclass_color_blue), getString(R.string.aclass_color_yellow))
            val colorCodes = arrayOf("#FFFFFF", "#E8F5E9", "#E3F2FD", "#FFFDE7")

            AlertDialog.Builder(this)
                .setTitle(getString(R.string.aclass_color_title))
                .setItems(colors) { _, which ->
                    selectedColor = colorCodes[which]
                    btnColor.backgroundTintList = android.content.res.ColorStateList.valueOf(android.graphics.Color.parseColor(selectedColor))
                }
                .show()
        }
    }

    private fun fetchTeachers() {
        val retrofit = RetrofitClient.getInstance(this)
        val api = retrofit.create(AddClassApi::class.java)

        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.

        lifecycleScope.launch(Dispatchers.IO) {
            try {
                teachersList = api.getTeachers()
                // FIX(null-data): نام ناقص/خالی نه «null» نشان می‌دهد و نه ردیف خالی می‌سازد؛
                // همان تبدیل در هر دو جای این تابع استفاده می‌شود تا انتخاب معلم همچنان تطبیق کند.
                val fallbackName = getString(R.string.common_person_unknown)
                val names = teachersList.map { "${it.first_name ?: ""} ${it.last_name ?: ""}".trim().ifEmpty { fallbackName } }

                withContext(Dispatchers.Main) {
                    val acTeacher = findViewById<AutoCompleteTextView>(R.id.acTeacher)
                    val adapter = ArrayAdapter(this@AddClassActivity, android.R.layout.simple_dropdown_item_1line, names)
                    acTeacher.setAdapter(adapter)

                    acTeacher.setOnItemClickListener { _, _, position, _ ->
                        val selectedName = adapter.getItem(position)
                        val teacher = teachersList.find { "${it.first_name ?: ""} ${it.last_name ?: ""}".trim().ifEmpty { fallbackName } == selectedName }
                        if (teacher != null) selectedTeacherId = teacher.id
                    }
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e; android.util.Log.e("AddClassActivity", "fetchTeachers failed", e) }
        }
    }

    private fun submitClass() {
        val title = findViewById<TextInputEditText>(R.id.etClassTitle).text.toString()
        val priceStr = findViewById<TextInputEditText>(R.id.etTeacherPrice).text.toString()

        if (title.isEmpty() || selectedTeacherId == -1 || priceStr.isEmpty()) {
            Toast.makeText(this, getString(R.string.aclass_fill_error), Toast.LENGTH_SHORT).show()
            return
        }

        // FIX: Bug 22 - reject negatives, malformed numbers and overflow without NumberFormatException.
        val price = InputValidation.nonNegativeAmount(priceStr)
        if (price == null) {
            findViewById<TextInputEditText>(R.id.etTeacherPrice).error = getString(R.string.aclass_price_error)
            return
        }

        val data = ClassSubmitData(
            title = title,
            code = "", // سرور به صورت خودکار کد ترتیبی ۶ رقمی اختصاص خواهد داد
            teacher_id = selectedTeacherId,
            education_type = findViewById<AutoCompleteTextView>(R.id.acEduType).text.toString(),
            grade_level = findViewById<AutoCompleteTextView>(R.id.acGrade).text.toString(),
            gender_type = "مختلط",
            days_of_week = "نامشخص",
            class_time = "نامشخص",
            teacher_session_price = price,
            bg_color = selectedColor,
            is_admin_created = isAdminMode
        )

        val retrofit = RetrofitClient.getInstance(this)
        val api = retrofit.create(AddClassApi::class.java)

        fun executeSubmit(override: Boolean) {
            // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
            lifecycleScope.launch(Dispatchers.IO) {
                try {
                    val response = api.createClass(data, override)
                    withContext(Dispatchers.Main) {
                        if (response.status == "warning") {
                            AlertDialog.Builder(this@AddClassActivity)
                                .setTitle(getString(R.string.aclass_conflict_title))
                                .setMessage(getString(R.string.aclass_conflict_msg, response.message))
                                .setPositiveButton(getString(R.string.invoice_confirm_yes)) { _, _ ->
                                    executeSubmit(override = true)
                                }
                                .setNegativeButton(getString(R.string.action_cancel), null)
                                .show()
                        } else {
                            // پس از ثبت موفق، هم ادمین و هم مربی مستقیماً بدون اتلاف وقت به صفحه افزودن دانش‌آموز منتقل می‌شوند
                            val intent = Intent(this@AddClassActivity, ClassSetupActivity::class.java)
                            intent.putExtra("CLASS_ID", response.id)
                            intent.putExtra("CLASS_NAME", title)
                            startActivity(intent)
                            finish()
                        }
                    }
                } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                    withContext(Dispatchers.Main) {
                        Toast.makeText(this@AddClassActivity, getString(R.string.aclass_submit_error), Toast.LENGTH_LONG).show()
                    }
                }
            }
        }

        executeSubmit(override = false)
    }
}
