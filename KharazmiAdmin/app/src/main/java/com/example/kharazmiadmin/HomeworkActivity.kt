package com.example.kharazmiadmin

import android.content.Context
import android.content.Intent
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
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import retrofit2.http.*
import java.text.DecimalFormat

// API Models for Homework
data class HomeworkCreateRequest(
    val course_id: Int,
    val title: String,
    val description: String,
    val due_date: String,
    val max_score: Float = 20.0f
)

data class HomeworkResponseModel(
    val id: Int,
    val course_id: Int,
    val course_title: String,
    val title: String,
    val description: String,
    val due_date: String,
    val max_score: Float,
    val status: String,
    val created_at: String
)

data class HomeworkItem(
    val id: Int,
    val course_title: String,
    val title: String,
    val description: String,
    val due_date: String,
    val max_score: Float,
    val status: String,
    val score: Float?,
    val feedback: String?
)

data class HomeworkSubmissionItem(
    val id: Int,
    val homework_id: Int,
    val student_id: Int,
    val student_name: String,
    val file_path: String?,
    val status: String,
    val score: Float?,
    val feedback: String?
)

data class GradeSubmissionRequest(
    val score: Float,
    val feedback: String
)

interface HomeworkNetworkApi {
    @POST("homework/create")
    suspend fun createHomework(@Body req: HomeworkCreateRequest): HomeworkResponseModel

    @DELETE("homework/{id}")
    suspend fun deleteHomework(@Path("id") id: Int): SimpleResponse

    @GET("homework/student/list")
    suspend fun getStudentHomeworks(): List<HomeworkItem>

    @POST("homework/submissions/{id}/grade")
    suspend fun gradeSubmission(@Path("id") subId: Int, @Body req: GradeSubmissionRequest): SimpleResponse

    @GET("homework/parent/child/{student_id}")
    suspend fun getParentChildHomeworks(@Path("student_id") studentId: Int): List<HomeworkItem>
}

class HomeworkActivity : BaseActivity() {

    private lateinit var flipper: ViewFlipper
    private lateinit var rvHomeworks: RecyclerView
    private lateinit var cardAdd: MaterialCardView
    private lateinit var etTitle: TextInputEditText
    private lateinit var etDesc: TextInputEditText
    private lateinit var etDueDate: TextInputEditText
    private lateinit var btnSubmit: Button

    // Details page
    private lateinit var tvHwDetailTitle: TextView
    private lateinit var tvHwDetailDesc: TextView
    private lateinit var tvHwDetailDueDate: TextView
    private lateinit var btnBack: Button

    // Conditional details parts
    private lateinit var llStudentSubmit: View
    private lateinit var btnUpload: Button
    private lateinit var llTeacherSubmissions: View
    private lateinit var rvSubmissions: RecyclerView

    private lateinit var api: HomeworkNetworkApi
    private var role: String = "student"
    private var activeCourseId: Int = -1
    private var studentIdForParent: Int = -1

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_homework_list)

        // Read active role and credentials
        val credsPrefs = getSharedPreferences("UserCreds", Context.MODE_PRIVATE)
        role = credsPrefs.getString("USER_SUB_ROLE", "student") ?: "student"

        activeCourseId = intent.getIntExtra("COURSE_ID", -1)
        studentIdForParent = intent.getIntExtra("STUDENT_ID", -1)

        initViews()
        setupApi()
        setupListeners()
        loadHomeworks()
    }

    private fun initViews() {
        flipper = findViewById(R.id.homeworkFlipper)
        rvHomeworks = findViewById(R.id.rvHomeworks)
        cardAdd = findViewById(R.id.cardAddHomework)
        etTitle = findViewById(R.id.etHwTitle)
        etDesc = findViewById(R.id.etHwDesc)
        etDueDate = findViewById(R.id.etHwDueDate)
        btnSubmit = findViewById(R.id.btnSubmitHomework)

        tvHwDetailTitle = findViewById(R.id.tvHwDetailTitle)
        tvHwDetailDesc = findViewById(R.id.tvHwDetailDesc)
        tvHwDetailDueDate = findViewById(R.id.tvHwDetailDueDate)
        btnBack = findViewById(R.id.btnBackToList)

        llStudentSubmit = findViewById(R.id.llStudentSubmitSection)
        btnUpload = findViewById(R.id.btnUploadFile)
        llTeacherSubmissions = findViewById(R.id.llTeacherSubmissionsSection)
        rvSubmissions = findViewById(R.id.rvSubmissions)

        rvHomeworks.layoutManager = LinearLayoutManager(this)
        rvSubmissions.layoutManager = LinearLayoutManager(this)

        // Show/hide based on role
        if (role == "teacher") {
            cardAdd.visibility = View.VISIBLE
        } else {
            cardAdd.visibility = View.GONE
        }
    }

    private fun setupApi() {
        val retrofit = RetrofitClient.getInstance(this)
        api = retrofit.create(HomeworkNetworkApi::class.java)
    }

    private fun setupListeners() {
        btnSubmit.setOnClickListener {
            val title = etTitle.text.toString().trim()
            val desc = etDesc.text.toString().trim()
            val due = etDueDate.text.toString().trim()

            if (title.isEmpty() || due.isEmpty()) {
                Toast.makeText(this, getString(R.string.hw_fill), Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }

            if (activeCourseId == -1) {
                Toast.makeText(this, getString(R.string.hw_class_bad), Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }

            createHomeworkOnServer(title, desc, due)
        }

        btnBack.setOnClickListener {
            flipper.displayedChild = 0 // Transition back to Homework list
        }
    }

    private fun createHomeworkOnServer(title: String, desc: String, due: String) {
        val req = HomeworkCreateRequest(activeCourseId, title, desc, due)
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val res = api.createHomework(req)
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@HomeworkActivity, getString(R.string.hw_created), Toast.LENGTH_LONG).show()
                    etTitle.text = null
                    etDesc.text = null
                    etDueDate.text = null
                    loadHomeworks() // Reload list
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@HomeworkActivity, getString(R.string.hw_create_error), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun loadHomeworks() {
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val list = when (role) {
                    "parent" -> api.getParentChildHomeworks(studentIdForParent)
                    else -> api.getStudentHomeworks()
                }
                withContext(Dispatchers.Main) {
                    // Filter list by active course if any is passed
                    val filteredList = if (activeCourseId != -1) {
                        // Normally course filtering can be done here if needed
                        list
                    } else {
                        list
                    }
                    bindHomeworksList(filteredList)
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@HomeworkActivity, getString(R.string.hw_load_error), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun bindHomeworksList(list: List<HomeworkItem>) {
        rvHomeworks.adapter = HomeworkAdapter(list) { hw ->
            showHomeworkDetails(hw)
        }
    }

    private fun showHomeworkDetails(hw: HomeworkItem) {
        flipper.displayedChild = 1 // Transition to details flipper state
        tvHwDetailTitle.text = hw.title
        tvHwDetailDesc.text = hw.description
        tvHwDetailDueDate.text = getString(R.string.hw_due_row, hw.due_date)

        // Conditional views for role
        if (role == "student") {
            llStudentSubmit.visibility = View.VISIBLE
            llTeacherSubmissions.visibility = View.GONE
            
            btnUpload.setOnClickListener {
                // Trigger file submission simulated flow
                submitMockSubmission(hw.id)
            }
        } else if (role == "teacher") {
            llStudentSubmit.visibility = View.GONE
            llTeacherSubmissions.visibility = View.VISIBLE
            loadSubmissionsForTeacher(hw.id)
        } else {
            // Parent view is read-only
            llStudentSubmit.visibility = View.GONE
            llTeacherSubmissions.visibility = View.GONE
        }
    }

    private fun submitMockSubmission(homeworkId: Int) {
        // Simulate a secure file upload successfully!
        Toast.makeText(this, getString(R.string.hw_file_loading), Toast.LENGTH_SHORT).show()
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.Main) {
            delay(1000)
            Toast.makeText(this@HomeworkActivity, getString(R.string.hw_file_done), Toast.LENGTH_LONG).show()
            flipper.displayedChild = 0 // Go back
            loadHomeworks()
        }
    }

    private fun loadSubmissionsForTeacher(homeworkId: Int) {
        // Mock submissions list for teacher grading
        val mockSubmissions = listOf(
            HomeworkSubmissionItem(1, homeworkId, 1, "الارا صیامی", "/uploads/homework/elara_math.pdf", "submitted", null, null),
            HomeworkSubmissionItem(2, homeworkId, 2, "فخرالنسا پوریافرانی", "/uploads/homework/fakhri_math.pdf", "submitted", null, null)
        )
        rvSubmissions.adapter = SubmissionsAdapter(mockSubmissions) { sub ->
            showGradingDialog(sub)
        }
    }

    private fun showGradingDialog(sub: HomeworkSubmissionItem) {
        val view = LayoutInflater.from(this).inflate(R.layout.activity_submit_grade, null)
        
        val etScore = view.findViewById<TextInputEditText>(R.id.etScore)
        val etDesc = view.findViewById<TextInputEditText>(R.id.etDesc)
        val tvHeader = view.findViewById<TextView>(R.id.tvSubmitGradeHeader)
        
        view.findViewById<TextView>(R.id.etExamTitle).visibility = View.GONE // Hide exam title input for homework grading
        
        tvHeader.text = getString(R.string.hw_grade_for, sub.student_name)
        etScore.setText("20")

        AlertDialog.Builder(this)
            .setTitle(getString(R.string.hw_grade_title))
            .setView(view)
            .setPositiveButton(getString(R.string.hw_grade_btn)) { _, _ ->
                val scoreVal = etScore.text.toString().toFloatOrNull() ?: 20.0f
                val feedbackText = etDesc.text.toString().trim()
                submitGradeToSever(sub.id, scoreVal, feedbackText)
            }
            .setNegativeButton(getString(R.string.common_cancel), null)
            .show()
    }

    private fun submitGradeToSever(submissionId: Int, score: Float, feedback: String) {
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                api.gradeSubmission(submissionId, GradeSubmissionRequest(score, feedback))
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@HomeworkActivity, getString(R.string.hw_grade_done), Toast.LENGTH_LONG).show()
                    flipper.displayedChild = 0 // Go back
                    loadHomeworks()
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@HomeworkActivity, getString(R.string.hw_grade_error), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }
}

class HomeworkAdapter(
    private val list: List<HomeworkItem>,
    private val onClick: (HomeworkItem) -> Unit
) : RecyclerView.Adapter<HomeworkAdapter.VH>() {

    class VH(v: View) : RecyclerView.ViewHolder(v) {
        val title: TextView = v.findViewById(R.id.tvHwTitle)
        val course: TextView = v.findViewById(R.id.tvHwCourseTitle)
        val date: TextView = v.findViewById(R.id.tvHwDueDate)
        val score: TextView = v.findViewById(R.id.tvHwScore)
        val feedback: TextView = v.findViewById(R.id.tvHwFeedback)
        val status: TextView = v.findViewById(R.id.tvHwStatus)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val v = LayoutInflater.from(parent.context).inflate(R.layout.item_homework, parent, false)
        return VH(v)
    }

    override fun onBindViewHolder(holder: VH, position: Int) {
        val item = list[position]
        holder.title.text = item.title
        holder.course.text = item.course_title
        holder.date.text = holder.itemView.context.getString(R.string.hw_due_short, item.due_date)

        val statusVal = item.status.lowercase()
        holder.status.text = when (statusVal) {
            "pending" -> holder.itemView.context.getString(R.string.hw_st_pending)
            "submitted" -> holder.itemView.context.getString(R.string.hw_st_submitted)
            "graded" -> holder.itemView.context.getString(R.string.hw_st_graded)
            "late" -> holder.itemView.context.getString(R.string.hw_st_late)
            else -> item.status
        }

        if (item.score != null) {
            holder.score.text = holder.itemView.context.getString(R.string.hw_score_row, item.score, item.max_score)
            holder.score.visibility = View.VISIBLE
        } else {
            holder.score.visibility = View.GONE
        }

        if (!item.feedback.isNullOrEmpty()) {
            holder.feedback.text = holder.itemView.context.getString(R.string.hw_feedback_row, item.feedback)
            holder.feedback.visibility = View.VISIBLE
        } else {
            holder.feedback.visibility = View.GONE
        }

        holder.itemView.setOnClickListener { onClick(item) }
    }

    override fun getItemCount() = list.size
}

class SubmissionsAdapter(
    private val list: List<HomeworkSubmissionItem>,
    private val onGradeClick: (HomeworkSubmissionItem) -> Unit
) : RecyclerView.Adapter<SubmissionsAdapter.VH>() {

    class VH(v: View) : RecyclerView.ViewHolder(v) {
        val name: TextView = v.findViewById(R.id.tvStudentName)
        val details: TextView = v.findViewById(R.id.tvSubmissionDetails)
        val btnGrade: MaterialButton = v.findViewById(R.id.btnGradeSubmission)
        val status: TextView = v.findViewById(R.id.tvSubmissionStatus)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val v = LayoutInflater.from(parent.context).inflate(R.layout.item_submission, parent, false)
        return VH(v)
    }

    override fun onBindViewHolder(holder: VH, position: Int) {
        val item = list[position]
        holder.name.text = item.student_name
        
        val statusVal = item.status.lowercase()
        holder.status.text = when (statusVal) {
            "submitted" -> holder.itemView.context.getString(R.string.hw_st_submitted)
            "graded" -> holder.itemView.context.getString(R.string.hw_st_graded)
            "late" -> holder.itemView.context.getString(R.string.hw_st_late2)
            else -> item.status
        }

        if (item.score != null) {
            holder.details.text = holder.itemView.context.getString(R.string.hw_det_row, item.score, item.feedback ?: "---")
        } else {
            holder.details.text = holder.itemView.context.getString(R.string.hw_det_wait)
        }

        holder.btnGrade.setOnClickListener { onGradeClick(item) }
    }

    override fun getItemCount() = list.size
}
