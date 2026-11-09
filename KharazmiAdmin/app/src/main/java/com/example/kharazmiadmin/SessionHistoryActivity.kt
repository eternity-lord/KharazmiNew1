package com.example.kharazmiadmin

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import android.widget.ImageView
import android.widget.Toast
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import retrofit2.http.Body
import retrofit2.http.POST

// مدل داده
data class HistoryRequest(val course_id: Int)
data class SessionHistoryItem(
    val session_id: Int, val date: String,
    val attendees: Int, val cost_per_student: Long, val total_cost: Long,
    val status: String? = "Finished",
    val start_time: String? = null,
    val end_time: String? = null
)

// API
interface HistoryApi {
    @POST("attendance/get_history")
    suspend fun getHistory(@Body req: HistoryRequest): List<SessionHistoryItem>
}

class SessionHistoryActivity : BaseActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_session_history)

        val classId = intent.getIntExtra("CLASS_ID", -1)
        val rv = findViewById<RecyclerView>(R.id.rvHistory)
        rv.layoutManager = LinearLayoutManager(this)

        if (classId != -1) {
            val retrofit = RetrofitClient.getInstance(this)
            val api = retrofit.create(HistoryApi::class.java)

            // FIX: Bug 19 - cancel screen work when this Activity is destroyed.

            lifecycleScope.launch(Dispatchers.IO) {
                try {
                    val list = api.getHistory(HistoryRequest(classId))
                    withContext(Dispatchers.Main) {
                        if (list.isEmpty()) Toast.makeText(this@SessionHistoryActivity, getString(R.string.shist_empty), Toast.LENGTH_SHORT).show()
                        rv.adapter = HistoryAdapter(list)
                    }
                } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                    withContext(Dispatchers.Main) { Toast.makeText(this@SessionHistoryActivity, getString(R.string.shist_error), Toast.LENGTH_SHORT).show() }
                }
            }
        }
    }
}

class HistoryAdapter(private val list: List<SessionHistoryItem>) : RecyclerView.Adapter<HistoryAdapter.VH>() {
    class VH(v: View) : RecyclerView.ViewHolder(v) {
        val date: TextView = v.findViewById(R.id.tvDate)
        val attendees: TextView = v.findViewById(R.id.tvAttendees)
        val cost: TextView = v.findViewById(R.id.tvCost)
        val tvStatus: TextView = v.findViewById(R.id.tvStatus)
        val imgStatusIcon: ImageView = v.findViewById(R.id.imgStatusIcon)
        val tvTime: TextView = v.findViewById(R.id.tvTime)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val v = LayoutInflater.from(parent.context).inflate(R.layout.item_session_history, parent, false)
        return VH(v)
    }

    override fun onBindViewHolder(holder: VH, position: Int) {
        val item = list[position]
        holder.date.text = holder.itemView.context.getString(R.string.shist_date, item.date)
        holder.attendees.text = holder.itemView.context.getString(R.string.shist_att, item.attendees)
        holder.cost.text = holder.itemView.context.getString(R.string.shist_cost, String.format("%,d", item.cost_per_student))

        // 🆕 نمایش زمان واقعی شروع/پایان جلسه (برای کلاس‌های زنده)
        if (!item.start_time.isNullOrEmpty()) {
            holder.tvTime.visibility = View.VISIBLE
            val end = item.end_time ?: ""
            holder.tvTime.text = if (end.isNotEmpty()) holder.itemView.context.getString(R.string.shist_time_full, item.start_time, end) else holder.itemView.context.getString(R.string.shist_time_start, item.start_time)
        } else {
            holder.tvTime.visibility = View.GONE
        }

        // نمایش بصری دقیق بر اساس وضعیت جلسه (عادی، اصلاح‌شده، حذف‌شده)
        val statusVal = item.status ?: "Finished"
        when (statusVal.lowercase()) {
            "finished" -> {
                holder.tvStatus.text = holder.itemView.context.getString(R.string.shist_st_done)
                holder.tvStatus.setTextColor(UiColors.resolve(holder.itemView.context, R.color.status_success))
                holder.imgStatusIcon.setImageResource(android.R.drawable.checkbox_on_background)
                holder.imgStatusIcon.imageTintList = android.content.res.ColorStateList.valueOf(UiColors.resolve(holder.itemView.context, R.color.status_success))
            }
            "modified" -> {
                holder.tvStatus.text = holder.itemView.context.getString(R.string.shist_st_modified)
                holder.tvStatus.setTextColor(UiColors.resolve(holder.itemView.context, R.color.status_warning))
                holder.imgStatusIcon.setImageResource(android.R.drawable.ic_menu_edit)
                holder.imgStatusIcon.imageTintList = android.content.res.ColorStateList.valueOf(UiColors.resolve(holder.itemView.context, R.color.status_warning))
            }
            "deleted" -> {
                holder.tvStatus.text = holder.itemView.context.getString(R.string.shist_st_deleted)
                holder.tvStatus.setTextColor(UiColors.resolve(holder.itemView.context, R.color.status_danger))
                holder.imgStatusIcon.setImageResource(android.R.drawable.ic_delete)
                holder.imgStatusIcon.imageTintList = android.content.res.ColorStateList.valueOf(UiColors.resolve(holder.itemView.context, R.color.status_danger))
            }
            else -> {
                holder.tvStatus.text = statusVal
                holder.tvStatus.setTextColor(UiColors.resolve(holder.itemView.context, R.color.text_secondary))
                holder.imgStatusIcon.setImageResource(android.R.drawable.checkbox_off_background)
                holder.imgStatusIcon.imageTintList = android.content.res.ColorStateList.valueOf(UiColors.resolve(holder.itemView.context, R.color.text_secondary))
            }
        }
    }

    override fun getItemCount() = list.size
}
