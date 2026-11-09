package com.example.kharazmiadmin

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.CheckBox
import android.widget.EditText
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.google.android.material.button.MaterialButton
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

// صف تایید ادمین: قرارداد قدیمی حفظ شده، اما پاسخ جدید conflict/capacity/audit را هم نمایش می‌دهد.
interface AdminClassApi {
    @GET("admin/pending_classes")
    suspend fun getPendingClasses(): List<PendingClassItem>

    @POST("admin/approve_class/{id}")
    suspend fun approveClass(@Path("id") id: Int): SimpleResponse

    @DELETE("admin/reject_class/{id}")
    suspend fun rejectClass(@Path("id") id: Int, @Query("reason") reason: String? = null): SimpleResponse
}

class PendingClassesActivity : BaseActivity() {

    private lateinit var rv: RecyclerView
    private lateinit var api: AdminClassApi
    private val selectedIds = linkedSetOf<Int>()
    private var pendingItems: List<PendingClassItem> = emptyList()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_pending_classes)

        rv = findViewById(R.id.rvPendingClasses)
        rv.layoutManager = LinearLayoutManager(this)
        api = RetrofitClient.getInstance(this).create(AdminClassApi::class.java)

        findViewById<Button>(R.id.btnPendingRefresh).setOnClickListener { fetchPending() }
        findViewById<Button>(R.id.btnPendingBulkApprove).setOnClickListener {
            if (selectedIds.isEmpty()) toast("حداقل یک کلاس را انتخاب کنید") else bulkApprove()
        }
        findViewById<Button>(R.id.btnPendingBulkReject).setOnClickListener {
            if (selectedIds.isEmpty()) toast("حداقل یک کلاس را انتخاب کنید") else showBulkRejectDialog()
        }
    }

    override fun onResume() {
        super.onResume()
        fetchPending()
    }

    private fun fetchPending() {
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val list = api.getPendingClasses()
                withContext(Dispatchers.Main) {
                    pendingItems = list
                    selectedIds.retainAll(list.map { it.id }.toSet())
                    if (list.isEmpty()) toast(getString(R.string.pcls_empty))
                    rv.adapter = PendingClassAdapter(
                        list = list,
                        selectedIds = selectedIds,
                        onSelectionChanged = { id, checked ->
                            if (checked) selectedIds.add(id) else selectedIds.remove(id)
                        },
                        onApproveClick = { approveClass(it) },
                        onRejectClick = { showRejectDialog(it) }
                    )
                }
            } catch (e: Exception) {
                if (e is kotlinx.coroutines.CancellationException) throw e
                withContext(Dispatchers.Main) { toast(getString(R.string.common_list_error)) }
            }
        }
    }

    private fun approveClass(id: Int) {
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val response = api.approveClass(id)
                withContext(Dispatchers.Main) {
                    selectedIds.remove(id)
                    toast(response.price_warning ?: response.message)
                    fetchPending()
                }
            } catch (e: Exception) {
                if (e is kotlinx.coroutines.CancellationException) throw e
                withContext(Dispatchers.Main) { toast("تأیید انجام نشد؛ تداخل زمان‌بندی یا وضعیت کلاس را بررسی کنید") }
            }
        }
    }

    private fun showRejectDialog(id: Int) {
        val input = EditText(this).apply { hint = "علت رد (الزامی)" }
        AlertDialog.Builder(this)
            .setTitle(getString(R.string.pcls_reject_title))
            .setMessage("رد کلاس باعث آرشیو شدن درخواست می‌شود و در ActivityLog ثبت خواهد شد.")
            .setView(input)
            .setPositiveButton(getString(R.string.common_delete_yes)) { _, _ ->
                val reason = input.text.toString().trim()
                if (reason.isEmpty()) toast("علت رد الزامی است") else rejectClass(id, reason)
            }
            .setNegativeButton(getString(R.string.action_cancel), null)
            .show()
    }

    private fun rejectClass(id: Int, reason: String) {
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val res = api.rejectClass(id, reason)
                withContext(Dispatchers.Main) {
                    selectedIds.remove(id)
                    toast(res.message)
                    fetchPending()
                }
            } catch (e: Exception) {
                if (e is kotlinx.coroutines.CancellationException) throw e
                withContext(Dispatchers.Main) { toast(getString(R.string.pcls_op_error)) }
            }
        }
    }

    private fun bulkApprove() {
        val ids = selectedIds.toList()
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                RetrofitClient.getInstance(this@PendingClassesActivity).create(ClassApi::class.java)
                    .bulkApprove(BulkClassDecisionRequest(ids))
                withContext(Dispatchers.Main) {
                    selectedIds.clear()
                    toast("${ids.size} کلاس تأیید شد")
                    fetchPending()
                }
            } catch (e: Exception) {
                if (e is kotlinx.coroutines.CancellationException) throw e
                withContext(Dispatchers.Main) { toast("تأیید گروهی انجام نشد؛ تداخل زمان‌بندی را بررسی کنید") }
            }
        }
    }

    private fun showBulkRejectDialog() {
        val input = EditText(this).apply { hint = "علت رد همه کلاس‌های انتخاب‌شده (الزامی)" }
        AlertDialog.Builder(this)
            .setTitle("رد گروهی درخواست‌ها")
            .setView(input)
            .setPositiveButton("ثبت رد") { _, _ ->
                val reason = input.text.toString().trim()
                if (reason.isEmpty()) toast("علت رد الزامی است") else bulkReject(reason)
            }
            .setNegativeButton(getString(R.string.action_cancel), null)
            .show()
    }

    private fun bulkReject(reason: String) {
        val ids = selectedIds.toList()
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                RetrofitClient.getInstance(this@PendingClassesActivity).create(ClassApi::class.java)
                    .bulkReject(BulkClassDecisionRequest(ids, reason))
                withContext(Dispatchers.Main) {
                    selectedIds.clear()
                    toast("${ids.size} کلاس رد شد")
                    fetchPending()
                }
            } catch (e: Exception) {
                if (e is kotlinx.coroutines.CancellationException) throw e
                withContext(Dispatchers.Main) { toast(getString(R.string.pcls_op_error)) }
            }
        }
    }

    private fun toast(message: String?) = Toast.makeText(this, message ?: "عملیات انجام شد", Toast.LENGTH_LONG).show()
}

class PendingClassAdapter(
    private val list: List<PendingClassItem>,
    private val selectedIds: Set<Int>,
    private val onSelectionChanged: (Int, Boolean) -> Unit,
    private val onApproveClick: (Int) -> Unit,
    private val onRejectClick: (Int) -> Unit
) : RecyclerView.Adapter<PendingClassAdapter.VH>() {

    class VH(v: View) : RecyclerView.ViewHolder(v) {
        val check: CheckBox = v.findViewById(R.id.cbPendingClass)
        val title: TextView = v.findViewById(R.id.tvTitle)
        val code: TextView = v.findViewById(R.id.tvCode)
        val teacher: TextView = v.findViewById(R.id.tvTeacher)
        val price: TextView = v.findViewById(R.id.tvPrice)
        val schedule: TextView = v.findViewById(R.id.tvSchedule)
        val issue: TextView = v.findViewById(R.id.tvPendingIssue)
        val btnApprove: MaterialButton = v.findViewById(R.id.btnApproveClass)
        val btnReject: MaterialButton = v.findViewById(R.id.btnRejectClass)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH = VH(
        LayoutInflater.from(parent.context).inflate(R.layout.item_pending_class, parent, false)
    )

    override fun onBindViewHolder(holder: VH, position: Int) {
        val item = list[position]
        holder.check.setOnCheckedChangeListener(null)
        holder.check.isChecked = selectedIds.contains(item.id)
        holder.check.setOnCheckedChangeListener { _, checked -> onSelectionChanged(item.id, checked) }
        holder.title.text = item.title?.takeIf { it.isNotBlank() } ?: "کلاس بدون عنوان"
        holder.code.text = holder.itemView.context.getString(R.string.pcls_code_row, item.code ?: item.id.toString())
        holder.teacher.text = holder.itemView.context.getString(R.string.pcls_teacher_row, item.teacher_name?.takeIf { it.isNotBlank() } ?: "نامشخص")
        holder.price.text = holder.itemView.context.getString(R.string.pcls_price_row, String.format("%,d", item.teacher_price ?: 0L))
        holder.schedule.text = holder.itemView.context.getString(R.string.pcls_sched_row, item.days ?: "روز نامشخص", item.time ?: "ساعت نامشخص")
        val conflictIds = item.conflict_course_ids.orEmpty()
        val conflicts = if (conflictIds.isEmpty()) "" else
            "⚠️ تداخل با کلاس‌های ${conflictIds.joinToString("، ")}"
        val rejection = item.rejection_reason?.takeIf { it.isNotBlank() }?.let { "علت رد قبلی: $it" } ?: ""
        holder.issue.text = listOf(conflicts, rejection).filter { it.isNotBlank() }.joinToString("\n")
        holder.issue.visibility = if (holder.issue.text.isNullOrBlank()) View.GONE else View.VISIBLE
        holder.btnApprove.setOnClickListener { onApproveClick(item.id) }
        holder.btnReject.setOnClickListener { onRejectClick(item.id) }
    }

    override fun getItemCount() = list.size
}
