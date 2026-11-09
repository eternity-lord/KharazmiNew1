package com.example.kharazmiadmin

import android.net.Uri
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.TextView
import android.widget.Toast
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

// تاریخچهٔ ادمین از endpoint گزارش می‌آید؛ بازگشایی فقط با guard مالی سرور انجام می‌شود.
data class AdminSessionHistoryResponse(val items: List<AdminSessionItem>, val count: Int)
data class AdminSessionItem(
    val id: Int, val course_title: String? = null, val date: String? = null,
    val time: String? = null, val status: String? = null, val teacher_name: String? = null,
    val attendance_count: Int = 0, val attendance: List<AdminAttendanceItem> = emptyList(),
    val financial_status: AdminFinancialStatus? = null,
    val problem_flags: List<String> = emptyList(), val reopen_allowed: Boolean = false
)
data class AdminAttendanceItem(
    val student_id: Int? = null, val student_name: String? = null,
    val status: String? = null, val excused: Boolean = false, val is_billed: Boolean = false
)
data class AdminFinancialStatus(
    val charge_amount: Long = 0, val billed_attendance_count: Int = 0,
    val penalty_settled: Boolean = false, val has_financial_effect: Boolean = false
)

interface AdminSessionHistoryApi {
    @GET("admin/session_history")
    suspend fun getHistory(
        @Query("date_from") dateFrom: String? = null,
        @Query("date_to") dateTo: String? = null,
        @Query("teacher_id") teacherId: Int? = null,
        @Query("course_id") courseId: Int? = null,
        @Query("flag") flag: String? = null,
        @Query("status") status: String? = null,
        @Query("search") search: String? = null
    ): AdminSessionHistoryResponse

    @POST("admin/session_history/{session_id}/reopen")
    suspend fun reopen(@Path("session_id") sessionId: Int, @Query("reason") reason: String): SimpleResponse
}

class AdminSessionHistoryActivity : BaseActivity() {
    private lateinit var adapter: AdminSessionHistoryAdapter
    private var filter: String? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_admin_session_history)
        val rv = findViewById<RecyclerView>(R.id.rvAdminSessionHistory)
        rv.layoutManager = LinearLayoutManager(this)
        adapter = AdminSessionHistoryAdapter(emptyList()) { item -> reopenSession(item) }
        rv.adapter = adapter
        findViewById<Button>(R.id.btnExportSessions).setOnClickListener { loadHistory(export = true) }
        findViewById<Button>(R.id.btnFilterSessions).setOnClickListener { loadHistory() }
        loadHistory()
    }

    private fun loadHistory(export: Boolean = false) {
        val flag = findViewById<TextView>(R.id.etSessionFlag).text.toString().trim().ifEmpty { null }
        val dateFrom = findViewById<TextView>(R.id.etSessionDateFrom).text.toString().trim().ifEmpty { null }
        val dateTo = findViewById<TextView>(R.id.etSessionDateTo).text.toString().trim().ifEmpty { null }
        val search = findViewById<TextView>(R.id.etSessionSearch).text.toString().trim().ifEmpty { null }
        val status = findViewById<TextView>(R.id.etSessionStatus).text.toString().trim().ifEmpty { null }
        val teacherId = findViewById<TextView>(R.id.etSessionTeacherId).text.toString().trim().toIntOrNull()
        val courseId = findViewById<TextView>(R.id.etSessionCourseId).text.toString().trim().toIntOrNull()
        filter = flag
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val historyApi = RetrofitClient.getInstance(this@AdminSessionHistoryActivity)
                    .create(AdminSessionHistoryApi::class.java)
                if (export) {
                    val base = RetrofitClient.getInstance(this@AdminSessionHistoryActivity).baseUrl().toString()
                    val url = Uri.parse("${base}admin/session_history").buildUpon()
                        .appendQueryParameter("date_from", dateFrom)
                        .appendQueryParameter("date_to", dateTo)
                        .appendQueryParameter("teacher_id", teacherId?.toString())
                        .appendQueryParameter("course_id", courseId?.toString())
                        .appendQueryParameter("flag", flag)
                        .appendQueryParameter("status", status)
                        .appendQueryParameter("search", search)
                        .appendQueryParameter("export", "true")
                        .build().toString()
                    ReportExporter.exportToExcel(
                        context = this@AdminSessionHistoryActivity,
                        endpointUrl = url,
                        fileName = "session_history_${System.currentTimeMillis()}.xlsx",
                        onStart = { Toast.makeText(this@AdminSessionHistoryActivity, "در حال ساخت خروجی جلسه‌ها…", Toast.LENGTH_SHORT).show() },
                        onComplete = { Toast.makeText(this@AdminSessionHistoryActivity, "خروجی جلسه‌ها آماده شد", Toast.LENGTH_LONG).show() },
                        onError = { Toast.makeText(this@AdminSessionHistoryActivity, "خروجی جلسه‌ها ناموفق بود: $it", Toast.LENGTH_LONG).show() }
                    )
                    return@launch
                }
                val response = historyApi.getHistory(
                    dateFrom = dateFrom, dateTo = dateTo, teacherId = teacherId, courseId = courseId,
                    flag = flag, status = status, search = search
                )
                withContext(Dispatchers.Main) { adapter.replace(response.items) }
            } catch (error: Exception) {
                if (error is kotlinx.coroutines.CancellationException) throw error
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@AdminSessionHistoryActivity, "دریافت تاریخچه ناموفق بود", Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun reopenSession(item: AdminSessionItem) {
        if (!item.reopen_allowed) {
            Toast.makeText(this, "این جلسه اثر مالی دارد و قابل بازگشایی نیست", Toast.LENGTH_LONG).show()
            return
        }
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                RetrofitClient.getInstance(this@AdminSessionHistoryActivity)
                    .create(AdminSessionHistoryApi::class.java).reopen(item.id, "اصلاح حضور و غیاب")
                withContext(Dispatchers.Main) { loadHistory() }
            } catch (error: Exception) {
                if (error is kotlinx.coroutines.CancellationException) throw error
                withContext(Dispatchers.Main) { Toast.makeText(this@AdminSessionHistoryActivity, "بازگشایی انجام نشد", Toast.LENGTH_SHORT).show() }
            }
        }
    }
}

class AdminSessionHistoryAdapter(
    private var items: List<AdminSessionItem>, private val onReopen: (AdminSessionItem) -> Unit
) : RecyclerView.Adapter<AdminSessionHistoryAdapter.VH>() {
    class VH(view: View) : RecyclerView.ViewHolder(view) {
        val title: TextView = view.findViewById(R.id.tvSessionTitle)
        val flags: TextView = view.findViewById(R.id.tvProblemFlags)
        val financial: TextView = view.findViewById(R.id.tvFinancialStatus)
        val attendance: TextView = view.findViewById(R.id.tvAttendanceDetails)
        val reopen: Button = view.findViewById(R.id.btnReopenSession)
    }
    override fun onCreateViewHolder(parent: ViewGroup, type: Int): VH = VH(
        LayoutInflater.from(parent.context).inflate(R.layout.item_admin_session_history, parent, false)
    )
    override fun onBindViewHolder(holder: VH, position: Int) {
        val item = items[position]
        holder.title.text = "${item.course_title ?: "کلاس"} | ${item.date ?: "تاریخ نامشخص"} ${item.time ?: ""}"
        holder.flags.text = "معلم: ${item.teacher_name ?: "بدون معلم"} | حضور: ${item.attendance_count} | " +
            if (item.problem_flags.isEmpty()) "بدون پرچم مشکل" else item.problem_flags.joinToString("، ")
        val financial = item.financial_status
        holder.financial.text = if (financial == null) "وضعیت مالی: نامشخص" else
            "مالی: ${financial.charge_amount} تومان | ثبت‌شده برای تسویه: ${financial.billed_attendance_count} | " +
                if (financial.has_financial_effect) "دارای اثر مالی" else "بدون اثر مالی"
        holder.attendance.text = if (item.attendance.isEmpty()) "حضور و غیاب: ثبت نشده" else
            "حضور و غیاب: " + item.attendance.joinToString("، ") {
                "${it.student_name ?: "دانش‌آموز نامشخص"}=${it.status ?: "نامشخص"}" +
                    if (it.is_billed) " [ثبت مالی]" else ""
            }
        holder.reopen.visibility = if (item.reopen_allowed) View.VISIBLE else View.GONE
        holder.reopen.setOnClickListener { onReopen(item) }
    }
    override fun getItemCount() = items.size
    fun replace(value: List<AdminSessionItem>) { items = value; notifyDataSetChanged() }
}
