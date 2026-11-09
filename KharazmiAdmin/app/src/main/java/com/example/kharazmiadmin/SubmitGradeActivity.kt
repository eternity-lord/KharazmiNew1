package com.example.kharazmiadmin

import android.os.Bundle
import android.widget.Button
import android.widget.Toast
import android.widget.TextView // FIX: Bug 22 - resolve the grade form header type.
import androidx.lifecycle.lifecycleScope
import com.google.android.material.textfield.TextInputEditText
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import retrofit2.http.Body
import retrofit2.http.POST
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

// ❌ کلاس GradeSubmitData از اینجا حذف شد (چون در AppModels.kt وجود دارد)

interface GradeApi {
    @POST("grades/submit")
    suspend fun submitGrade(@Body data: GradeSubmitData): SimpleResponse
}

class SubmitGradeActivity : BaseActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_submit_grade)

        val studentId = intent.getIntExtra("STUDENT_ID", -1)
        val courseId = intent.getIntExtra("COURSE_ID", -1)
        val studentName = intent.getStringExtra("STUDENT_NAME") ?: getString(R.string.classes_students)

        if (studentId == -1 || courseId == -1) {
            Toast.makeText(this, getString(R.string.sgrade_incomplete), Toast.LENGTH_SHORT).show()
            finish()
            return
        }

        val tvHeader = findViewById<TextView>(R.id.tvSubmitGradeHeader)
        if (tvHeader != null) {
            tvHeader.text = getString(R.string.sgrade_header, studentName)
        }

        // تنظیم عنوان صفحه (اختیاری)
        // supportActionBar?.title = "ثبت نمره برای $studentName"

        findViewById<Button>(R.id.btnSubmitGradeFinal).setOnClickListener {
            val title = findViewById<TextInputEditText>(R.id.etExamTitle).text.toString()
            val scoreStr = findViewById<TextInputEditText>(R.id.etScore).text.toString()
            val maxScoreStr = findViewById<TextInputEditText>(R.id.etMaxScore).text.toString()
            val desc = findViewById<TextInputEditText>(R.id.etDesc).text.toString()

            if (title.isEmpty() || scoreStr.isEmpty()) {
                Toast.makeText(this, getString(R.string.sgrade_required), Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }

            // FIX: Bug 22 - invalid/over-limit input must not crash or be submitted as a grade.
            val score = InputValidation.normalizeDigits(scoreStr).toFloatOrNull()
            val maximum = if (maxScoreStr.isBlank()) 20f else InputValidation.normalizeDigits(maxScoreStr).toFloatOrNull()
            if (score == null || maximum == null || !InputValidation.isValidScore(score, maximum)) {
                findViewById<TextInputEditText>(R.id.etScore).error = getString(R.string.sgrade_score_error)
                return@setOnClickListener
            }

            // حالا GradeSubmitData را از AppModels.kt می‌خواند
            val data = GradeSubmitData(
                student_id = studentId,
                course_id = courseId,
                exam_title = title,
                score = score, // FIX: Bug 22 - use the already validated values.
                max_score = maximum,
                date = SimpleDateFormat("yyyy/MM/dd", Locale.US).format(Date()),
                description = desc
            )

            sendGrade(data)
        }
    }

    private fun sendGrade(data: GradeSubmitData) {
        // FIX L9: ضد دابل‌کلیک — حین ارسال غیرفعال؛ موفقیت finish می‌کند پس بازگشت فقط در خطا.
        findViewById<Button>(R.id.btnSubmitGradeFinal).isEnabled = false
        val retrofit = RetrofitClient.getInstance(this)
        val api = retrofit.create(GradeApi::class.java)

        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.

        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val res = api.submitGrade(data)
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@SubmitGradeActivity, getString(R.string.common_ok_msg, res.message), Toast.LENGTH_LONG).show()
                    
                    // ابطال کش کارنامه دانش‌آموز
                    CacheManager.clear(this@SubmitGradeActivity, "student_grades_${data.student_id}")
                    
                    finish()
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@SubmitGradeActivity, getString(R.string.sgrade_error), Toast.LENGTH_SHORT).show()
                    findViewById<Button>(R.id.btnSubmitGradeFinal).isEnabled = true
                }
            }
        }
    }
}
