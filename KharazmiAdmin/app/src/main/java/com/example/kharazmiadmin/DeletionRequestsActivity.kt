package com.example.kharazmiadmin

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
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
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

// API
interface DeletionRequestApi {
    @GET("classes/deletion_requests")
    suspend fun getRequests(@Query("status") status: String? = null): List<DeletionRequestItem>

    @POST("classes/deletion_requests/{id}/approve")
    suspend fun approve(@Path("id") id: Int): SimpleResponse

    @POST("classes/deletion_requests/{id}/reject")
    suspend fun reject(@Path("id") id: Int, @Body req: DeletionRejectRequest): SimpleResponse
}

data class DeletionRejectRequest(val admin_note: String? = null)

data class DeletionRequestItem(
    val request_id: Int = -1,
    val course_id: Int = -1,
    val course_title: String? = null,
    val course_code: String? = null,
    val requested_by_role: String? = null,
    val requester_name: String? = null,
    val forgive_session_charges: Boolean = false,
    val status: String? = null,
    val admin_note: String? = null,
    val created_at: String? = null,
    val snapshot: DeletionSnapshot? = null
)

data class DeletionSnapshot(
    val sessions_total: Int = 0,
    val students: List<DeletionSnapshotStudent>? = null,
    val totals: DeletionSnapshotTotals? = null
)

data class DeletionSnapshotStudent(
    val name: String? = null,
    val sessions_attended: Int = 0,
    val tuition_final: Long = 0,
    val total_paid: Long = 0,
    val debt: Long = 0
)

data class DeletionSnapshotTotals(
    val students: Int = 0,
    val total_debt: Long = 0,
    val total_paid: Long = 0,
    val teacher_pending_this_class: Long = 0
)

class DeletionRequestsActivity : BaseActivity() {

    private lateinit var rv: RecyclerView
    private lateinit var api: DeletionRequestApi
    private var currentList: List<DeletionRequestItem> = emptyList()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_deletion_requests)

        rv = findViewById(R.id.rvPendingClasses)
        rv.layoutManager = LinearLayoutManager(this)

        val retrofit = RetrofitClient.getInstance(this)
        api = retrofit.create(DeletionRequestApi::class.java)
    }

    override fun onResume() {
        super.onResume()
        fetchPending() // رفرش لیست هر بار که به صفحه برمیگردیم
    }

    private fun fetchPending() {
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val list = api.getRequests("pending")
                withContext(Dispatchers.Main) {
                    currentList = list
                    if (list.isEmpty()) {
                        Toast.makeText(this@DeletionRequestsActivity, getString(R.string.delreq_empty), Toast.LENGTH_SHORT).show()
                    }
                    rv.adapter = DeletionRequestAdapter(
                        list,
                        onApprove = { id -> showApproveDialog(id) },
                        onReject = { id -> showRejectDialog(id) },
                        onDetail = { item -> showSnapshotDialog(item) }
                    )
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@DeletionRequestsActivity, getString(R.string.common_list_error), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun showApproveDialog(id: Int) {
        AlertDialog.Builder(this)
            .setTitle(getString(R.string.delreq_ok_title))
            .setMessage(getString(R.string.delreq_ok_msg))
            .setPositiveButton(getString(R.string.delreq_ok_yes)) { _, _ -> decide(id, true) }
            .setNegativeButton(getString(R.string.action_cancel), null)
            .show()
    }

    private fun showRejectDialog(id: Int) {
        AlertDialog.Builder(this)
            .setTitle(getString(R.string.delreq_no_title))
            .setMessage(getString(R.string.delreq_no_msg))
            .setPositiveButton(getString(R.string.delreq_no_yes)) { _, _ -> decide(id, false) }
            .setNegativeButton(getString(R.string.action_cancel), null)
            .show()
    }

    private fun decide(id: Int, approve: Boolean) {
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val res = if (approve) api.approve(id) else api.reject(id, DeletionRejectRequest(null))
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@DeletionRequestsActivity, getString(R.string.common_ok_msg, res.message), Toast.LENGTH_LONG).show()
                    fetchPending() // رفرش لیست
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@DeletionRequestsActivity, getString(R.string.delreq_op_error), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun showSnapshotDialog(item: DeletionRequestItem) {
        val snap = item.snapshot
        val sb = StringBuilder()
        sb.append(getString(R.string.delreq_det_class, item.course_title ?: "-", item.course_code ?: ""))
        sb.append(getString(R.string.delreq_det_requester, item.requester_name ?: "-", roleNameFa(item.requested_by_role)))
        sb.append(getString(R.string.delreq_det_forgive, if (item.forgive_session_charges) getString(R.string.common_yes) else getString(R.string.common_no)))
        if (snap != null) {
            val t = snap.totals
            sb.append(getString(R.string.delreq_det_sessions, snap.sessions_total))
            if (t != null) {
                sb.append(getString(R.string.delreq_det_debt, String.format("%,d", t.total_debt)))
                sb.append(getString(R.string.delreq_det_pending, String.format("%,d", t.teacher_pending_this_class)))
            }
            sb.append(getString(R.string.delreq_det_students))
            snap.students?.forEach { s ->
                sb.append(getString(R.string.delreq_det_student, s.name ?: "-", s.sessions_attended, String.format("%,d", s.debt)))
            }
        }
        AlertDialog.Builder(this)
            .setTitle(getString(R.string.delreq_det_title, item.request_id))
            .setMessage(sb.toString())
            .setPositiveButton(getString(R.string.btn_dismiss), null)
            .show()
    }

    private fun roleNameFa(role: String?): String = when (role) {
        "teacher" -> getString(R.string.delreq_role_teacher)
        "secretary" -> getString(R.string.delreq_role_secretary)
        "admin" -> getString(R.string.delreq_role_admin)
        else -> role ?: "-"
    }
}

class DeletionRequestAdapter(
    private val list: List<DeletionRequestItem>,
    private val onApprove: (Int) -> Unit,
    private val onReject: (Int) -> Unit,
    private val onDetail: (DeletionRequestItem) -> Unit
) : RecyclerView.Adapter<DeletionRequestAdapter.VH>() {

    class VH(v: View) : RecyclerView.ViewHolder(v) {
        val title: TextView = v.findViewById(R.id.tvTitle)
        val code: TextView = v.findViewById(R.id.tvCode)
        val teacher: TextView = v.findViewById(R.id.tvTeacher)
        val price: TextView = v.findViewById(R.id.tvPrice)
        val schedule: TextView = v.findViewById(R.id.tvSchedule)
        val btnApprove: MaterialButton = v.findViewById(R.id.btnApproveClass) // دکمه سبز
        val btnReject: MaterialButton = v.findViewById(R.id.btnRejectClass)   // دکمه قرمز
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val v = LayoutInflater.from(parent.context).inflate(R.layout.item_deletion_request, parent, false)
        return VH(v)
    }

    override fun onBindViewHolder(holder: VH, position: Int) {
        val item = list[position]
        val t = item.snapshot?.totals
        holder.title.text = item.course_title ?: holder.itemView.context.getString(R.string.delreq_row_title, item.course_id)
        holder.code.text = holder.itemView.context.getString(R.string.delreq_row_code, item.request_id, item.created_at ?: "")
        val roleFa = when (item.requested_by_role) {
            "teacher" -> holder.itemView.context.getString(R.string.delreq_role_teacher)
            "secretary" -> holder.itemView.context.getString(R.string.delreq_role_secretary)
            else -> item.requested_by_role ?: "-"
        }
        holder.teacher.text = holder.itemView.context.getString(R.string.delreq_row_requester, item.requester_name ?: "-", roleFa)
        holder.price.text = holder.itemView.context.getString(R.string.delreq_row_debt, String.format("%,d", t?.total_debt ?: 0))
        holder.schedule.text = holder.itemView.context.getString(R.string.delreq_row_stats, t?.students ?: 0, item.snapshot?.sessions_total ?: 0, if (item.forgive_session_charges) holder.itemView.context.getString(R.string.common_yes) else holder.itemView.context.getString(R.string.common_no))
        holder.btnApprove.setOnClickListener { onApprove(item.request_id) }
        holder.btnReject.setOnClickListener { onReject(item.request_id) }
        holder.itemView.setOnClickListener { onDetail(item) }
    }

    override fun getItemCount() = list.size
}
