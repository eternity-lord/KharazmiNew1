package com.example.kharazmiadmin

import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import android.widget.Toast
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

// ==========================================
// 📡 صفحه‌ی «کلاس‌های در حال برگزاری» (ادمین/منشی)
// Polling ساده با Handler؛ هر ۱۵ ثانیه. هیچ کش‌هایی روی این صفحه استفاده نمی‌شود
// چون داده لحظه‌ای است (بخش ۴ هماهنگی).
// ==========================================

class LiveClassesActivity : BaseActivity() {

    private lateinit var api: LiveApi
    private lateinit var rv: RecyclerView
    private lateinit var tvEmpty: TextView
    private var liveItems: List<LiveSessionItem> = emptyList()

    private val handler = Handler(Looper.getMainLooper())
    // جلوگیری از انباشته‌شدن درخواست‌های هم‌زمان (اگر درخواستی هنوز باز باشد، تیک بعدی رد می‌شود)
    private val pollInFlight = java.util.concurrent.atomic.AtomicBoolean(false)
    private val pollRunnable = object : Runnable {
        override fun run() {
            if (!pollInFlight.get()) {
                fetchLiveSessions()
            }
            handler.postDelayed(this, 15000) // 15 ثانیه
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_live_classes)

        rv = findViewById(R.id.rvLiveClasses)
        tvEmpty = findViewById(R.id.tvLiveEmpty)
        rv.layoutManager = LinearLayoutManager(this)

        api = RetrofitClient.getInstance(this).create(LiveApi::class.java)

        fetchLiveSessions()
        handler.post(pollRunnable)
    }

    override fun onDestroy() {
        super.onDestroy()
        handler.removeCallbacks(pollRunnable)
    }

    override fun onResume() {
        super.onResume()
        // رفرش سریع هنگام بازگشت
        fetchLiveSessions()
    }

    private fun fetchLiveSessions() {
        if (!pollInFlight.compareAndSet(false, true)) return
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val list = api.getLiveSessions()
                liveItems = list
                withContext(Dispatchers.Main) {
                    tvEmpty.visibility = if (list.isEmpty()) View.VISIBLE else View.GONE
                    rv.adapter = LiveClassesAdapter(list) { item ->
                        val intent = Intent(this@LiveClassesActivity, LiveRosterActivity::class.java)
                        intent.putExtra("LIVE_SESSION_ID", item.liveSessionId)
                        intent.putExtra("CLASS_TITLE", item.classTitle)
                        startActivity(intent)
                    }

                    // تعداد زنده به عنوان عنوان
                    findViewById<TextView>(R.id.tvLiveClassesTitle).text =
                        getString(R.string.lclss_title_count, list.size)
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    if (liveItems.isEmpty()) {
                        tvEmpty.visibility = View.VISIBLE
                        tvEmpty.text = getString(R.string.lclss_poll_error)
                    }
                }
            } finally {
                pollInFlight.set(false)
            }
        }
    }
}

class LiveClassesAdapter(
    private val list: List<LiveSessionItem>,
    private val onClick: (LiveSessionItem) -> Unit
) : RecyclerView.Adapter<LiveClassesAdapter.VH>() {

    class VH(v: View) : RecyclerView.ViewHolder(v) {
        val title: TextView = v.findViewById(R.id.tvLiveClassTitle)
        val teacher: TextView = v.findViewById(R.id.tvLiveTeacher)
        val elapsed: TextView = v.findViewById(R.id.tvLiveElapsed)
        val present: TextView = v.findViewById(R.id.tvLivePresent)
        val absent: TextView = v.findViewById(R.id.tvLiveAbsent)
        val undetermined: TextView = v.findViewById(R.id.tvLiveUndetermined)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val v = LayoutInflater.from(parent.context).inflate(R.layout.item_live_class, parent, false)
        return VH(v)
    }

    override fun onBindViewHolder(holder: VH, position: Int) {
        val item = list[position]
        holder.title.text = holder.itemView.context.getString(R.string.lclss_class_row, item.classTitle, item.courseCode)
        holder.teacher.text = holder.itemView.context.getString(R.string.lclss_teacher_row, item.teacherName)
        holder.elapsed.text = holder.itemView.context.getString(R.string.lclss_elapsed, item.elapsedMinutes)
        holder.present.text = holder.itemView.context.getString(R.string.lclss_present, item.present)
        holder.absent.text = holder.itemView.context.getString(R.string.lclss_absent, item.absent)
        holder.undetermined.text = holder.itemView.context.getString(R.string.lclss_undet, item.undetermined)
        holder.itemView.setOnClickListener { onClick(item) }
    }

    override fun getItemCount() = list.size
}
