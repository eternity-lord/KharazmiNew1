package com.example.kharazmiadmin

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.*
import androidx.appcompat.app.AlertDialog
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.google.android.material.button.MaterialButton
import com.google.android.material.card.MaterialCardView
import com.google.android.material.textfield.TextInputEditText
import kotlinx.coroutines.*
import retrofit2.http.*
import java.text.DecimalFormat

// API Models for Exam System
data class AttemptStartResponse(
    val attempt_id: Int,
    val duration: Int,
    val questions: List<QuestionItem>
)

data class QuestionItem(
    val id: Int,
    val question_text: String,
    val type: String,
    val options: List<String>
)

data class ReportCardResponse(
    val student_name: String,
    val national_code: String,
    val overall_average: Float,
    val courses: List<ReportCardCourseItem>,
    val comments: String,
    val final_status: String
)

data class ReportCardCourseItem(
    val course_title: String,
    val teacher_name: String,
    val attendance_percentage: Float,
    val grades: List<ReportCardGradeItem>,
    val average_score: Float
)

data class ReportCardGradeItem(
    val title: String,
    val score: Float,
    val max_score: Float
)

data class AnswerItem(
    val question_id: Int,
    val answer_text: String
)

data class AttemptSubmitRequest(
    val answers: List<AnswerItem>
)

data class AttemptSubmitResponse(
    val message: String,
    val is_graded: Boolean,
    val score: Float?
)

interface ExamNetworkApi {
    @GET("exams/student/list")
    suspend fun getExams(): List<HomeworkItem>

    @POST("exams/attempts/{exam_id}/start")
    suspend fun startAttempt(@Path("exam_id") examId: Int): AttemptStartResponse

    @POST("exams/attempts/{attempt_id}/submit")
    suspend fun submitAttempt(@Path("attempt_id") attemptId: Int, @Body req: AttemptSubmitRequest): AttemptSubmitResponse

    @GET("students/{id}/report_card")
    suspend fun getReportCard(@Path("id") id: Int): ReportCardResponse
}

class ExamActivity : BaseActivity() {

    private lateinit var flipper: ViewFlipper
    private lateinit var rvExams: RecyclerView
    private lateinit var btnViewReportCard: Button

    // Attempt State views
    private lateinit var tvActiveExamTitle: TextView
    private lateinit var tvExamTimer: TextView
    private lateinit var tvQuestionNumber: TextView
    private lateinit var tvQuestionText: TextView
    private lateinit var rgOptions: RadioGroup
    private lateinit var rbOption1: RadioButton
    private lateinit var rbOption2: RadioButton
    private lateinit var rbOption3: RadioButton
    private lateinit var rbOption4: RadioButton
    private lateinit var tilShortAnswer: View
    private lateinit var etAnswerText: TextInputEditText
    private lateinit var btnSubmit: Button

    private lateinit var api: ExamNetworkApi
    private var role: String = "student"
    private var studentId: Int = -1
    private var activeAttemptId: Int = -1
    private var activeQuestions: List<QuestionItem> = emptyList()
    private var currentQuestionIndex: Int = 0
    private val submittedAnswers = ArrayList<AnswerItem>()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_exam_list)

        val credsPrefs = getSharedPreferences("UserCreds", Context.MODE_PRIVATE)
        role = credsPrefs.getString("USER_SUB_ROLE", "student") ?: "student"
        studentId = credsPrefs.getInt("USER_ID", -1)

        initViews()
        setupApi()
        setupListeners()
        loadExams()
    }

    private fun initViews() {
        flipper = findViewById(R.id.examFlipper)
        rvExams = findViewById(R.id.rvExams)
        btnViewReportCard = findViewById(R.id.btnViewReportCard)

        tvActiveExamTitle = findViewById(R.id.tvActiveExamTitle)
        tvExamTimer = findViewById(R.id.tvExamTimer)
        tvQuestionNumber = findViewById(R.id.tvQuestionNumber)
        tvQuestionText = findViewById(R.id.tvQuestionText)
        rgOptions = findViewById(R.id.rgOptions)
        rbOption1 = findViewById(R.id.rbOption1)
        rbOption2 = findViewById(R.id.rbOption2)
        rbOption3 = findViewById(R.id.rbOption3)
        rbOption4 = findViewById(R.id.rbOption4)
        tilShortAnswer = findViewById(R.id.tilShortAnswer)
        etAnswerText = findViewById(R.id.etAnswerText)
        btnSubmit = findViewById(R.id.btnSubmitExam)

        rvExams.layoutManager = LinearLayoutManager(this)

        if (role in listOf("student", "parent")) {
            btnViewReportCard.visibility = View.VISIBLE
        } else {
            btnViewReportCard.visibility = View.GONE
        }
    }

    private fun setupApi() {
        val retrofit = RetrofitClient.getInstance(this)
        api = retrofit.create(ExamNetworkApi::class.java)
    }

    private fun setupListeners() {
        btnViewReportCard.setOnClickListener {
            loadAndDisplayReportCard()
        }
    }

    private fun loadExams() {
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val list = api.getExams()
                withContext(Dispatchers.Main) {
                    if (list.isEmpty()) {
                        Toast.makeText(this@ExamActivity, getString(R.string.exam_empty), Toast.LENGTH_SHORT).show()
                    }
                    rvExams.adapter = HomeworkAdapter(list) { exam ->
                        if (exam.status.lowercase() == "pending") {
                            promptStartExam(exam.id, exam.title)
                        } else {
                            Toast.makeText(this@ExamActivity, getString(R.string.exam_joined), Toast.LENGTH_SHORT).show()
                        }
                    }
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@ExamActivity, getString(R.string.exam_list_error), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun promptStartExam(examId: Int, title: String) {
        AlertDialog.Builder(this)
            .setTitle(getString(R.string.exam_start_title, title))
            .setMessage(getString(R.string.exam_start_msg))
            .setPositiveButton(getString(R.string.exam_start_btn)) { _, _ ->
                startExamAttemptOnServer(examId)
            }
            .setNegativeButton(getString(R.string.common_cancel), null)
            .show()
    }

    private fun startExamAttemptOnServer(examId: Int) {
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val res = api.startAttempt(examId)
                withContext(Dispatchers.Main) {
                    activeAttemptId = res.attempt_id
                    activeQuestions = res.questions
                    currentQuestionIndex = 0
                    submittedAnswers.clear()
                    
                    flipper.displayedChild = 1 // Switch to active exam state
                    displayActiveQuestion()
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@ExamActivity, getString(R.string.exam_start_error), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun displayActiveQuestion() {
        if (currentQuestionIndex >= activeQuestions.size) {
            submitAllAnswersToServer()
            return
        }

        val q = activeQuestions[currentQuestionIndex]
        tvQuestionNumber.text = getString(R.string.exam_q_number, currentQuestionIndex + 1, activeQuestions.size)
        tvQuestionText.text = q.question_text

        // Style the input widgets based on type
        if (q.type == "multiple_choice" || q.type == "true_false") {
            rgOptions.visibility = View.VISIBLE
            tilShortAnswer.visibility = View.GONE
            rgOptions.clearCheck()

            if (q.options.size >= 2) {
                rbOption1.text = q.options[0]
                rbOption2.text = q.options[1]
                rbOption1.visibility = View.VISIBLE
                rbOption2.visibility = View.VISIBLE
            } else {
                rbOption1.visibility = View.GONE
                rbOption2.visibility = View.GONE
            }

            if (q.options.size >= 4) {
                rbOption3.text = q.options[2]
                rbOption4.text = q.options[3]
                rbOption3.visibility = View.VISIBLE
                rbOption4.visibility = View.VISIBLE
            } else {
                rbOption3.visibility = View.GONE
                rbOption4.visibility = View.GONE
            }
        } else {
            rgOptions.visibility = View.GONE
            tilShortAnswer.visibility = View.VISIBLE
            etAnswerText.text = null
        }

        btnSubmit.text = if (currentQuestionIndex == activeQuestions.size - 1) getString(R.string.exam_finish_btn) else getString(R.string.exam_next_btn)
        btnSubmit.setOnClickListener {
            saveCurrentAnswerAndGoNext()
        }
    }

    private fun saveCurrentAnswerAndGoNext() {
        val q = activeQuestions[currentQuestionIndex]
        var answer = ""

        if (q.type == "multiple_choice" || q.type == "true_false") {
            answer = when (rgOptions.checkedRadioButtonId) {
                R.id.rbOption1 -> rbOption1.text.toString()
                R.id.rbOption2 -> rbOption2.text.toString()
                R.id.rbOption3 -> rbOption3.text.toString()
                R.id.rbOption4 -> rbOption4.text.toString()
                else -> ""
            }
        } else {
            answer = etAnswerText.text.toString().trim()
        }

        submittedAnswers.add(AnswerItem(q.id, answer))
        currentQuestionIndex++
        displayActiveQuestion()
    }

    private fun submitAllAnswersToServer() {
        Toast.makeText(this, getString(R.string.exam_submitting), Toast.LENGTH_SHORT).show()
        val req = AttemptSubmitRequest(submittedAnswers)
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val res = api.submitAttempt(activeAttemptId, req)
                withContext(Dispatchers.Main) {
                    AlertDialog.Builder(this@ExamActivity)
                        .setTitle(getString(R.string.exam_done_title))
                        .setMessage(getString(R.string.exam_result_msg, res.message, if (res.is_graded) getString(R.string.exam_score_is, res.score) else getString(R.string.exam_descriptive)))
                        .setPositiveButton(getString(R.string.common_understood)) { _, _ ->
                            flipper.displayedChild = 0 // Back to list
                            loadExams()
                        }
                        .setCancelable(false)
                        .show()
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@ExamActivity, getString(R.string.exam_submit_error), Toast.LENGTH_SHORT).show()
                    flipper.displayedChild = 0
                }
            }
        }
    }

    private fun loadAndDisplayReportCard() {
        val targetId = if (role == "parent") intent.getIntExtra("STUDENT_ID", -1) else studentId
        if (targetId == -1) {
            Toast.makeText(this, getString(R.string.exam_sid_bad), Toast.LENGTH_SHORT).show()
            return
        }

        Toast.makeText(this, getString(R.string.exam_report_loading), Toast.LENGTH_SHORT).show()
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val card = api.getReportCard(targetId)
                withContext(Dispatchers.Main) {
                    showGraphicalReportCard(card, targetId)
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@ExamActivity, getString(R.string.exam_report_error), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun showGraphicalReportCard(card: ReportCardResponse, studentId: Int) {
        val dialogView = LayoutInflater.from(this).inflate(R.layout.activity_student_profile, null)
        
        // Hide unrelated views to re-purpose profile as a gorgeous graphical Report Card!
        dialogView.findViewById<View>(R.id.tabLayoutProfile).visibility = View.GONE
        dialogView.findViewById<View>(R.id.btnIssueInvoice).visibility = View.GONE
        dialogView.findViewById<View>(R.id.btnSendPortalLink).visibility = View.GONE
        dialogView.findViewById<View>(R.id.btnDeleteStudent).visibility = View.GONE
        dialogView.findViewById<View>(R.id.fabEditProfile).visibility = View.GONE
        
        val tvName = dialogView.findViewById<TextView>(R.id.tvProfileName)
        val tvPhone = dialogView.findViewById<TextView>(R.id.tvProfilePhone)
        val tvContent = dialogView.findViewById<TextView>(R.id.tvContent)
        
        tvName.text = card.student_name
        tvPhone.text = getString(R.string.exam_card_row, card.national_code, card.overall_average)
        
        val builder = StringBuilder()
        builder.append(getString(R.string.exam_rep_detail))
        for (course in card.courses) {
            builder.append(getString(R.string.exam_rep_course, course.course_title, course.teacher_name))
            builder.append(getString(R.string.exam_rep_avg, course.average_score, course.attendance_percentage))
            if (course.grades.isNotEmpty()) {
                val gradesText = course.grades.joinToString("، ") { getString(R.string.exam_rep_grade, it.title, it.score) }
                builder.append(getString(R.string.exam_rep_grades, gradesText))
            }
            builder.append("\n")
        }
        builder.append(getString(R.string.exam_rep_feedback, card.comments))
        builder.append(getString(R.string.exam_rep_final, card.final_status))
        
        tvContent.text = builder.toString()

        val dialog = AlertDialog.Builder(this)
            .setView(dialogView)
            .setCancelable(true)
            .create()
            
        // Re-purpose cardFinancialStatus to act as download PDF button!
        val cardPdf = dialogView.findViewById<MaterialCardView>(R.id.cardFinancialStatus)
        val tvTotalDebt = dialogView.findViewById<TextView>(R.id.tvTotalDebt)
        tvTotalDebt.text = getString(R.string.exam_pdf_hint)
        tvTotalDebt.setTextColor(UiColors.resolve(this@ExamActivity, R.color.status_info))
        
        dialogView.findViewById<View>(R.id.tvDebtTeacher).visibility = View.GONE
        dialogView.findViewById<View>(R.id.tvDebtInstitute).visibility = View.GONE

        cardPdf.setOnClickListener {
            downloadReportCardPdf(studentId)
        }

        dialog.show()
    }

    private fun downloadReportCardPdf(studentId: Int) {
        val token = SecureLoginStore.getToken(this)  // FIX M22: توکن از حافظه‌ی رمزشده.
        
        val retrofit = RetrofitClient.getInstance(this)
        val baseUrl = retrofit.baseUrl().toString()
        val url = "${baseUrl}students/$studentId/report_card/pdf"
        
        Toast.makeText(this, getString(R.string.exam_pdf_downloading), Toast.LENGTH_SHORT).show()
        
        val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url)).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        startActivity(intent)
    }
}
