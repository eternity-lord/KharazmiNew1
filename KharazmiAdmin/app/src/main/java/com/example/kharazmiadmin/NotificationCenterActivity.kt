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
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path

// گروه‌های فیلتر اعلان — منطبق با typeهای واقعیِ تولیدشده در سرور
// (installment/payment = مالی، attendance = حضور و غیاب، بقیه ⇒ «سیستمی و کلاس»)
private val MONEY_TYPES = setOf("installment", "payment")
private val ATTENDANCE_TYPES = setOf("attendance")

// API Models for Notification Center
// FIX(admin-notifications): این ستون‌ها در دیتابیس nullable هستند (رکوردهای legacy) و سرور
// می‌تواند null برگرداند؛ با نوع non-null، Gson مقدار null را روی فیلد Kotlin می‌گذاشت و
// اولین استفاده (bind در adapter یا دیالوگ جزئیات) با NPE کرش می‌کرد.
data class NotificationItem(
    val id: Int,
    val type: String? = null,
    val title: String? = null,
    val body: String? = null,
    val is_read: Boolean? = null,
    val created_at: String? = null
)

// FIX(admin-notifications): پاسخ endpoint شمارش خوانده‌نشده‌ها (GET /notifications/unread_count)
data class UnreadCountResponse(
    val unread: Int? = null,
    val total: Int? = null
)

interface NotificationCenterApi {
    @GET("notifications")
    suspend fun getNotifications(): List<NotificationItem>

    // FIX(admin-notifications): endpoint شمارش خوانده‌نشده‌ها (قبلاً وجود نداشت)
    @GET("notifications/unread_count")
    suspend fun getUnreadCount(): UnreadCountResponse

    @POST("notifications/{id}/read")
    suspend fun markRead(@Path("id") id: Int): SimpleResponse

    @POST("notifications/read_all")
    suspend fun markAllRead(): SimpleResponse
}

class NotificationCenterActivity : BaseActivity() {

    private lateinit var rv: RecyclerView
    private lateinit var btnMarkAll: MaterialButton
    private lateinit var btnFilter: MaterialButton
    // FIX(admin-notifications): نمایش شمارش خوانده‌نشده‌ها + حالت خالی
    private lateinit var tvUnreadCount: TextView
    private lateinit var tvEmpty: TextView

    private lateinit var api: NotificationCenterApi
    private var allNotifications: List<NotificationItem> = emptyList()
    private var activeFilterType: String? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_notification_list)

        initViews()
        setupApi()
        setupListeners()
        // FIX(admin-notifications): بارگذاری به onResume منتقل شد (قبلاً فقط یک‌بار در onCreate
        // بود ⇒ بعد از ثبت/تغییر داده یا بازگشت به صفحه، لیست کهنه می‌ماند و اعلان تازه دیده نمی‌شد).
    }

    override fun onResume() {
        super.onResume()
        loadNotifications()
    }

    private fun initViews() {
        rv = findViewById(R.id.rvNotifications)
        btnMarkAll = findViewById(R.id.btnMarkAllRead)
        btnFilter = findViewById(R.id.btnFilterNotifs)
        tvUnreadCount = findViewById(R.id.tvUnreadCount)
        tvEmpty = findViewById(R.id.tvNotifEmpty)

        rv.layoutManager = LinearLayoutManager(this)
    }

    private fun setupApi() {
        val retrofit = RetrofitClient.getInstance(this)
        api = retrofit.create(NotificationCenterApi::class.java)
    }

    private fun setupListeners() {
        btnMarkAll.setOnClickListener {
            AlertDialog.Builder(this)
                .setTitle(getString(R.string.notif_readall_title))
                .setMessage(getString(R.string.notif_readall_msg))
                .setPositiveButton(getString(R.string.common_yes)) { _, _ ->
                    markAllAsRead()
                }
                .setNegativeButton(getString(R.string.common_cancel), null)
                .show()
        }

        btnFilter.setOnClickListener {
            showFilterDialog()
        }
    }

    private fun loadNotifications() {
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val list = api.getNotifications()
                // شمارش خوانده‌نشده‌ها خطای جدا دارد: شکست آن نباید لیست را از بین ببرد.
                val unread = try {
                    api.getUnreadCount().unread ?: 0
                } catch (e: Exception) {
                    if (e is kotlinx.coroutines.CancellationException) throw e
                    0
                }
                withContext(Dispatchers.Main) {
                    allNotifications = list
                    updateUnreadCount(unread)
                    applyFilterAndBind()
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    // FIX(admin-notifications): خطا لیست را پاک می‌کند تا داده‌ی کهنه/گیج‌کننده
                    // نماند و پیام روشن نشان داده می‌شود (قبلاً فقط Toast بود و لیست قبلی می‌ماند).
                    allNotifications = emptyList()
                    updateUnreadCount(0)
                    applyFilterAndBind()
                    Toast.makeText(this@NotificationCenterActivity, getString(R.string.notif_list_error), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    // FIX(admin-notifications): نمایش تعداد خوانده‌نشده‌ها بالای لیست
    private fun updateUnreadCount(count: Int) {
        if (count > 0) {
            tvUnreadCount.visibility = View.VISIBLE
            tvUnreadCount.text = getString(R.string.notif_unread_count, count)
        } else {
            tvUnreadCount.visibility = View.GONE
        }
    }

    // FIX(admin-notifications): گروه‌بندی فیلتر با typeهای واقعیِ سرور
    // (installment/payment/attendance/grade/homework/exam/message/announcement/automation).
    // قبلاً فقط تطبیق دقیق با "system" بود ⇒ type="automation" (نوع اصلی اعلان ادمین)
    // زیر فیلتر «سیستمی و کلاس» نمایش داده نمی‌شد.
    private fun matchesFilter(item: NotificationItem): Boolean {
        val filter = activeFilterType ?: return true
        val type = item.type?.lowercase()
        return when (filter) {
            "money" -> type in MONEY_TYPES
            "attendance" -> type in ATTENDANCE_TYPES
            else -> type == null || (type !in MONEY_TYPES && type !in ATTENDANCE_TYPES)
        }
    }

    private fun applyFilterAndBind() {
        val filtered = allNotifications.filter { matchesFilter(it) }
        if (filtered.isEmpty()) {
            tvEmpty.visibility = View.VISIBLE
            tvEmpty.text = if (allNotifications.isEmpty()) {
                getString(R.string.notif_empty)
            } else {
                getString(R.string.notif_empty_filter)
            }
            rv.visibility = View.GONE
        } else {
            tvEmpty.visibility = View.GONE
            rv.visibility = View.VISIBLE
        }
        rv.adapter = NotificationAdapter(filtered) { notif ->
            showNotificationDetailDialog(notif)
        }
    }

    private fun markAllAsRead() {
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                api.markAllRead()
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@NotificationCenterActivity, getString(R.string.notif_all_read), Toast.LENGTH_SHORT).show()
                    loadNotifications() // Reload
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@NotificationCenterActivity, getString(R.string.notif_status_error), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun showNotificationDetailDialog(item: NotificationItem) {
        // Mark as read immediately on open
        // FIX(admin-notifications): is_read ممکن است NULL باشد (رکورد legacy) ⇒ «خوانده‌نشده»
        // حساب می‌شود (is_read != true) و نه با `!item.is_read` روی Boolean nullable.
        if (item.is_read != true) {
            // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
            lifecycleScope.launch(Dispatchers.IO) {
                try {
                    api.markRead(item.id)
                    withContext(Dispatchers.Main) {
                        loadNotifications() // Reload list silently
                    }
                } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e; android.util.Log.e("NotificationCenterActivity", "showNotificationDetailDialog failed", e) }
            }
        }

        // Show Details Dialog
        // FIX(admin-notifications): متن‌ها null-safe شدند (title/body/created_at می‌توانند NULL باشند).
        AlertDialog.Builder(this)
            .setTitle(item.title ?: getString(R.string.notif_untitled))
            .setMessage("${item.created_at ?: ""}\n\n${item.body ?: ""}")
            .setPositiveButton(getString(R.string.common_understood), null)
            .show()
    }

    private fun showFilterDialog() {
        val types = arrayOf(getString(R.string.notif_f_all), getString(R.string.notif_f_att), getString(R.string.notif_f_money), getString(R.string.notif_f_sys))
        // FIX(admin-notifications): کلید گروه «مالی» = money (شامل installment و payment)
        val typeCodes = arrayOf(null, "attendance", "money", "system")

        AlertDialog.Builder(this)
            .setTitle(getString(R.string.notif_filter_title))
            .setItems(types) { _, which ->
                activeFilterType = typeCodes[which]
                btnFilter.text = if (activeFilterType == null) getString(R.string.notif_filter_btn) else getString(R.string.notif_filter_on, types[which])
                applyFilterAndBind()
            }
            .show()
    }
}

class NotificationAdapter(
    private val list: List<NotificationItem>,
    private val onClick: (NotificationItem) -> Unit
) : RecyclerView.Adapter<NotificationAdapter.VH>() {

    class VH(v: View) : RecyclerView.ViewHolder(v) {
        val title: TextView = v.findViewById(R.id.tvNotifTitle)
        val date: TextView = v.findViewById(R.id.tvNotifDate)
        val body: TextView = v.findViewById(R.id.tvNotifBody)
        val unread: View = v.findViewById(R.id.vUnreadIndicator)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val v = LayoutInflater.from(parent.context).inflate(R.layout.item_notification, parent, false)
        return VH(v)
    }

    override fun onBindViewHolder(holder: VH, position: Int) {
        val item = list[position]
        // FIX(admin-notifications): فیلدهای nullable با fallback امن (بدون NPE/متن null خالی)
        val ctx = holder.itemView.context
        holder.title.text = item.title ?: ctx.getString(R.string.notif_untitled)
        holder.date.text = item.created_at ?: ""
        holder.body.text = item.body ?: ""

        // کنترل دیداری نشانگر اعلان‌های خوانده نشده (is_read=NULL ⇒ خوانده‌نشده)
        if (item.is_read == true) {
            holder.unread.visibility = View.GONE
        } else {
            holder.unread.visibility = View.VISIBLE
        }

        holder.itemView.setOnClickListener { onClick(item) }
    }

    override fun getItemCount() = list.size
}
