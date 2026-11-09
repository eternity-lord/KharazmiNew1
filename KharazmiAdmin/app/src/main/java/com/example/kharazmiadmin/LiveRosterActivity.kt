package com.example.kharazmiadmin

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.ImageButton
import android.widget.TextView
import android.widget.Toast
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

// ==========================================
// 📇 صفحه‌ی «جزئیات زنده‌ی کلاس» برای ادمین/منشی
// لیست کامل دانش‌آموزان با وضعیت لحظه‌ای + دو آیکون تماس (خودش / والدین)
// Polling ساده با Handler؛ هر ۱۸ ثانیه. از داده‌ی شبکه‌ی لحظه‌ای استفاده می‌کند
// و از کش ذخیره نمی‌شود (چون داده زنده است).
// ==========================================

class LiveRosterActivity : BaseActivity() {

    private var liveSessionId: Int = -1
    private lateinit var api: LiveApi
    private lateinit var rv: RecyclerView
    private lateinit var tvClassInfo: TextView
    private lateinit var tvElapsed: TextView
    private lateinit var tvSummary: TextView
    private lateinit var tvEmpty: TextView

    private val handler = Handler(Looper.getMainLooper())
    // جلوگیری از انباشته‌شدن درخواست‌های هم‌زمان
    private val pollInFlight = java.util.concurrent.atomic.AtomicBoolean(false)
    private val pollRunnable = object : Runnable {
        override fun run() {
            if (!pollInFlight.get()) {
                fetchRoster()
            }
            handler.postDelayed(this, 18000) // 18 ثانیه
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_live_roster)

        liveSessionId = intent.getIntExtra("LIVE_SESSION_ID", -1)
        val classTitle = intent.getStringExtra("CLASS_TITLE") ?: ""

        tvClassInfo = findViewById(R.id.tvRosterClassInfo)
        tvElapsed = findViewById(R.id.tvRosterElapsed)
        tvSummary = findViewById(R.id.tvRosterSummary)
        tvEmpty = findViewById(R.id.tvRosterEmpty)
        rv = findViewById(R.id.rvRoster)
        rv.layoutManager = LinearLayoutManager(this)

        tvClassInfo.text = getString(R.string.lrost_class_row, classTitle)

        api = RetrofitClient.getInstance(this).create(LiveApi::class.java)

        fetchRoster()
        handler.post(pollRunnable)
    }

    override fun onDestroy() {
        super.onDestroy()
        handler.removeCallbacks(pollRunnable)
    }

    override fun onResume() {
        super.onResume()
        fetchRoster()
    }

    private fun fetchRoster() {
        if (liveSessionId <= 0) return
        if (!pollInFlight.compareAndSet(false, true)) return
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val data = api.getLiveRoster(liveSessionId)
                withContext(Dispatchers.Main) {
                    tvClassInfo.text = getString(R.string.lrost_class_full, data.classTitle, data.teacherName)
                    tvElapsed.text = getString(R.string.lrost_elapsed, data.elapsedMinutes)
                    tvSummary.text = getString(R.string.lrost_summary, data.present, data.absent, data.undetermined)
                    tvEmpty.visibility = if (data.students.isEmpty()) View.VISIBLE else View.GONE
                    rv.adapter = LiveRosterAdapter(data.students)
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    if (liveSessionId != -1) {
                        Toast.makeText(this@LiveRosterActivity, getString(R.string.lrost_live_error), Toast.LENGTH_SHORT).show()
                    }
                }
            } finally {
                pollInFlight.set(false)
            }
        }
    }
}

class LiveRosterAdapter(
    private val list: List<LiveRosterStudent>
) : RecyclerView.Adapter<LiveRosterAdapter.VH>() {

    class VH(v: View) : RecyclerView.ViewHolder(v) {
        val name: TextView = v.findViewById(R.id.tvRosterName)
        val status: TextView = v.findViewById(R.id.tvRosterStatus)
        val studentPhone: TextView = v.findViewById(R.id.tvRosterStudentPhone)
        val parentPhone: TextView = v.findViewById(R.id.tvRosterParentPhone)
        val btnCallStudent: ImageButton = v.findViewById(R.id.btnCallStudent)
        val btnCallParent: ImageButton = v.findViewById(R.id.btnCallParent)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val v = LayoutInflater.from(parent.context).inflate(R.layout.item_live_roster, parent, false)
        return VH(v)
    }

    override fun onBindViewHolder(holder: VH, position: Int) {
        val item = list[position]
        holder.name.text = item.studentName

        // رنگ وضعیت وضعیت‌ها (بدون تغییر پالت برند/وضعیتی)
        when (item.status) {
            "Present", "Late" -> {
                holder.status.text = if (item.status == "Late") holder.itemView.context.getString(R.string.lrost_late) else holder.itemView.context.getString(R.string.lrost_present)
                holder.status.setTextColor(UiColors.resolve(holder.itemView.context, R.color.status_success))
            }
            "Absent" -> {
                holder.status.text = if (item.excused) holder.itemView.context.getString(R.string.lrost_excused) else holder.itemView.context.getString(R.string.lrost_absent)
                holder.status.setTextColor(UiColors.resolve(holder.itemView.context, R.color.status_danger))
            }
            else -> {
                holder.status.text = holder.itemView.context.getString(R.string.lrost_unknown)
                holder.status.setTextColor(UiColors.resolve(holder.itemView.context, R.color.status_warning))
            }
        }

        holder.studentPhone.text = holder.itemView.context.getString(R.string.lrost_st_phone, item.studentMobile.ifEmpty { holder.itemView.context.getString(R.string.lrost_unset) })
        holder.parentPhone.text = holder.itemView.context.getString(R.string.lrost_par_phone, item.parentMobile.ifEmpty { holder.itemView.context.getString(R.string.lrost_unset) })

        holder.btnCallStudent.setOnClickListener {
            call(holder.itemView, item.studentMobile)
        }
        holder.btnCallParent.setOnClickListener {
            call(holder.itemView, item.parentMobile)
        }

        holder.itemView.setOnClickListener {
            val intent = Intent(holder.itemView.context, StudentProfileActivity::class.java)
            intent.putExtra("STUDENT_ID", item.studentId)
            holder.itemView.context.startActivity(intent)
        }
    }

    override fun getItemCount() = list.size

    private fun call(view: View, phone: String) {
        if (phone.isNotEmpty()) {
            val intent = Intent(Intent.ACTION_DIAL, Uri.parse("tel:$phone"))
            view.context.startActivity(intent)
        } else {
            Toast.makeText(view.context, view.context.getString(R.string.lrost_no_phone), Toast.LENGTH_SHORT).show()
        }
    }
}
