package com.example.kharazmiadmin

import android.content.Context
import android.content.Intent
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.Bundle
import android.util.Log
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.RadioButton
import android.widget.RadioGroup
import android.widget.TextView
import android.widget.Toast
import android.widget.ImageView
import androidx.appcompat.app.AlertDialog
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.google.android.material.button.MaterialButton
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import retrofit2.HttpException
import retrofit2.http.Body
import retrofit2.http.POST
import retrofit2.http.GET
import retrofit2.http.PUT
import java.io.IOException
import kotlin.math.abs

// API داخلی برای ثبت جلسه (بقیه از فایل ApiInterfaces خوانده می‌شوند)
interface AttendanceSubmitApi {
    @POST("attendance/submit_session")
    suspend fun submitSession(@Body data: SessionSubmitData): SessionResponse

    @GET("attendance/session/{session_code}")
    suspend fun getSessionDetails(@retrofit2.http.Path("session_code") sessionCode: Int): SessionDetailsResponse

    @PUT("attendance/session/{session_code}")
    suspend fun editSession(
        @retrofit2.http.Path("session_code") sessionCode: Int,
        @Body data: SessionSubmitData
    ): SessionResponse
}

data class SessionDetailsResponse(
    val session_id: Int,
    val session_code: Int,
    val course_id: Int,
    val class_title: String,
    val class_code: String,
    val teacher_name: String,
    val date: String,
    val attendee_count: Int,
    val items: List<SessionItemDetails>
)

data class SessionItemDetails(
    val student_id: Int,
    val name: String,
    val status: String,
    val excused: Boolean,
    val student_code: Int?
)

class AttendanceActivity : BaseActivity() {

    private var classId: Int = -1
    private var mode: String = "NEW_SESSION" // "NEW_SESSION" or "EDIT_SESSION"
    private var targetSessionCode: Int = -1
    private var editSessionDate: String? = null // FIX (audit-v2/#13): تاریخ اصلی جلسه در حالت ویرایش (نه امروز)

    private lateinit var apiDetails: InvoiceApi // ✅ استفاده از اینترفیس عمومی
    private lateinit var apiSubmit: AttendanceSubmitApi
    private lateinit var classApi: ClassApi // FIX(null-class): انتخابگر کلاس در مسیر منو
    private lateinit var rv: RecyclerView

    private val attendanceMap = HashMap<Int, String>() // ID -> Status
    private val excusedMap = HashMap<Int, Boolean>() // ID -> Excused Status (موجه / غیرموجه)
    private var studentList: List<StudentItem> = listOf()
    private lateinit var tvNetworkStatus: TextView

    // FIX C10-B2: guard against overlapping queue flushes (onResume can fire while one runs).
    @Volatile private var isFlushingQueue = false
    // FIX C10-B3: live connectivity callback (registered in onStart, released in onStop — never leaks).
    private var networkCallback: ConnectivityManager.NetworkCallback? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_attendance)

        classId = intent.getIntExtra("TARGET_COURSE_ID", -1)
        val className = intent.getStringExtra("TARGET_COURSE_NAME") ?: ""
        mode = intent.getStringExtra("MODE") ?: "NEW_SESSION"
        targetSessionCode = intent.getIntExtra("TARGET_SESSION_CODE", -1)

        tvNetworkStatus = findViewById(R.id.tvNetworkStatus)
        // نمایش صادقانه‌ی وضعیت اتصال واقعی (بدون شبیه‌سازی دستی)
        refreshNetworkStatus()

        if (mode == "EDIT_SESSION") {
            findViewById<TextView>(R.id.tvPageTitle).text = getString(R.string.attendance_edit_title_code, targetSessionCode)
        } else {
            findViewById<TextView>(R.id.tvPageTitle).text = getString(R.string.attendance_title_class, className)
            findViewById<TextView>(R.id.etSessionDate).text = JalaliUtils.todayJalaliString() // FIX (audit-v2/#13): نمایش تاریخ شمسی امروز (قبلاً خالی بود)
        }

        rv = findViewById(R.id.rvAttendanceList)
        rv.layoutManager = LinearLayoutManager(this)

        val retrofit = RetrofitClient.getInstance(this)
        apiDetails = retrofit.create(InvoiceApi::class.java)
        apiSubmit = retrofit.create(AttendanceSubmitApi::class.java)
        classApi = retrofit.create(ClassApi::class.java)

        if (mode == "EDIT_SESSION") {
            loadSessionDetailsForEdit()
        } else if (classId > 0) {
            fetchStudents()
        } else {
            // FIX(null-class): مسیر منوی اصلی بدون class ID — هرگز با -1 به سرور نمی‌رویم؛
            // به‌جای آن انتخابگر کلاس معتبر باز می‌شود.
            showClassPickerDialog()
        }

        findViewById<MaterialButton>(R.id.btnFinishSession).setOnClickListener {
            promptConfirmSession()
        }

        // FIX C10-B3-step5: restore rotation-saved entries (loaders use putIfAbsent, so any order is safe).
        savedInstanceState?.let { state ->
            @Suppress("UNCHECKED_CAST", "DEPRECATION")
            val savedAtt = state.getSerializable("attendance_map") as? HashMap<Int, String>
            @Suppress("UNCHECKED_CAST", "DEPRECATION")
            val savedExc = state.getSerializable("excused_map") as? HashMap<Int, Boolean>
            savedAtt?.let { attendanceMap.putAll(it) }
            savedExc?.let { excusedMap.putAll(it) }
        }
    }

    override fun onSaveInstanceState(outState: Bundle) {
        // FIX C10-B3-step5: rotation/process-death no longer wipes the filled form.
        outState.putSerializable("attendance_map", HashMap(attendanceMap))
        outState.putSerializable("excused_map", HashMap(excusedMap))
        super.onSaveInstanceState(outState)
    }

    override fun onResume() {
        super.onResume()
        // به‌روزرسانی صادقانه‌ی وضعیت اتصال هر بار که به صفحه برمی‌گردیم
        refreshNetworkStatus()
        // FIX C10-B2: quiet flush of the offline queue (see flushPendingQueue: never interrupts current work).
        flushPendingQueue()
        // FIX C10-B3: re-render the queue card on every return (covers externally-changed queue).
        refreshQueueCard()
    }

    override fun onStart() {
        super.onStart()
        // FIX C10-B3: live connectivity callback — auto-flush as soon as the network returns.
        // registerDefaultNetworkCallback needs API 24+; minSdk is exactly 24.
        val cm = getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val cb = object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network: android.net.Network) {
                runOnUiThread {
                    refreshNetworkStatus()
                    flushPendingQueue() // guarded by isFlushingQueue: never overlaps onResume's flush
                }
            }

            override fun onLost(network: android.net.Network) {
                runOnUiThread { refreshNetworkStatus() }
            }
        }
        networkCallback = cb
        cm.registerDefaultNetworkCallback(cb)
    }

    override fun onStop() {
        // FIX C10-B3: always release the callback — never leaks past the visible lifetime.
        networkCallback?.let {
            (getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager)
                .unregisterNetworkCallback(it)
            networkCallback = null
        }
        super.onStop()
    }

    /**
     * FIX C10-B2: quiet auto-flush of the offline queue (+ C10-B3: refreshes the queue card).
     * - Runs only when online; overlaps prevented by [isFlushingQueue].
     * - Never shows dialogs, never touches the on-screen form (attendanceMap/studentList).
     * - At most ONE summary Toast, and only if something was actually sent/resolved/failed.
     * - FAILED items (server errors) are left for manual attention (B3 card) — not auto-retried.
     * - Stale SENDING items (a previous flush died mid-flight) are retried: only one flush runs
     *   at a time, so SENDING always means "interrupted", never "in progress elsewhere".
     */
    /**
     * FIX (کلاس-مالی/تازگی): کش سبک صفحهٔ کلاس برای همین کلاس را باطل می‌کند.
     *
     * چرا لازم است؟ ثبت/ویرایش جلسه، بدهی و درآمد کلاس را عوض می‌کند، ولی کش `class_report_*`
     * و `class_students_full_*` دست‌نخورده می‌ماند. اگر کاربر بعد از ثبت، صفحهٔ کلاس را با شبکهٔ
     * قطع (fallback کش ≤۵ دقیقه) باز کند، صفحهٔ کلاس اعداد *قبل از جلسه* را نشان می‌دهد؛ همان باگ
     * «درآمد وصول شده / بدهی به معلم / بدهی به آموزشگاه = ۰ بعد از برگزاری جلسه». الگوی موجود
     * پروژه: `ClassSetupActivity` و `StudentRegisterActivity` هم بعد از تغییر ثبت‌نام همین دو کلید
     * را پاک می‌کنند؛ اینجا همان کار برای تغییر جلسه انجام می‌شود (منطق مالی هیچ تغییری نمی‌کند).
     */
    private fun invalidateClassCaches(courseId: Int) {
        CacheManager.clear(this, "class_report_$courseId")
        CacheManager.clear(this, "class_students_full_$courseId")
    }

    private fun flushPendingQueue() {
        if (!isNetworkAvailable()) return
        if (isFlushingQueue) return
        isFlushingQueue = true
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                var sent = 0
                var resolvedDup = 0
                var failed = 0
                val pending = PendingAttendanceStore.getAll(this@AttendanceActivity)
                    .filter { it.status != PendingAttendanceStore.Status.FAILED }
                for (item in pending) {
                    when (sendQueueItem(item)) {
                        QueueSendResult.SENT -> sent++
                        QueueSendResult.ALREADY_REGISTERED -> resolvedDup++
                        QueueSendResult.NETWORK_DOWN -> break
                        QueueSendResult.FAILED -> failed++
                    }
                }
                withContext(Dispatchers.Main) {
                    refreshQueueCard()
                    if (sent + resolvedDup + failed > 0) {
                        val parts = mutableListOf<String>()
                        if (sent > 0) parts.add(getString(R.string.attendance_queue_sent, sent))
                        if (resolvedDup > 0) parts.add(getString(R.string.attendance_queue_dup, resolvedDup))
                        if (failed > 0) parts.add(getString(R.string.attendance_queue_failed, failed))
                        Toast.makeText(this@AttendanceActivity, getString(R.string.attendance_queue_summary, parts.joinToString("؛ ")), Toast.LENGTH_LONG).show()
                    }
                }
            } finally {
                isFlushingQueue = false
            }
        }
    }

    /** FIX C10-B3: outcome of one queued-item send (the store is already updated inside). */
    private enum class QueueSendResult { SENT, ALREADY_REGISTERED, NETWORK_DOWN, FAILED }

    /**
     * FIX C10-B3: sends ONE queued item (shared by auto-flush and manual retry).
     * Suspend; call from Dispatchers.IO. Updates the store, never touches UI.
     */
    private suspend fun sendQueueItem(item: PendingAttendanceStore.PendingItem): QueueSendResult {
        PendingAttendanceStore.updateStatus(
            this, item.id,
            PendingAttendanceStore.Status.SENDING, incTries = true
        )
        return try {
            val payload = SessionSubmitData(
                item.courseId, item.date,
                item.items.map { SessionItem(it.student_id, it.status, it.excused) }
            )
            if (item.op == PendingAttendanceStore.Op.EDIT && item.targetSessionCode != null) {
                apiSubmit.editSession(item.targetSessionCode, payload)
            } else {
                apiSubmit.submitSession(payload)
            }
            PendingAttendanceStore.remove(this, item.id)
            // FIX (کلاس-مالی/تازگی): ارسال موفق از صف آفلاین هم مثل ثبت آنلاین، اعداد مالی کلاس را
            // عوض کرده؛ کش صفحهٔ همان کلاس پاک می‌شود تا صفحه snapshot قبل از جلسه را نشان ندهد.
            invalidateClassCaches(item.courseId)
            QueueSendResult.SENT
        } catch (e: Exception) {
            // FIX: Bug 19 - cancellation is not a network/UI error.
            if (e is kotlinx.coroutines.CancellationException) throw e
            when (e) {
                is java.io.IOException -> {
                    // Network dropped mid-send: keep the item queued.
                    PendingAttendanceStore.updateStatus(
                        this, item.id,
                        PendingAttendanceStore.Status.PENDING, getString(R.string.attendance_queue_offline)
                    )
                    QueueSendResult.NETWORK_DOWN
                }
                is retrofit2.HttpException -> {
                    if (e.code() == 409) {
                        // Already registered (e.g. from another device) — not an error.
                        PendingAttendanceStore.remove(this, item.id)
                        // FIX (کلاس-مالی/تازگی): جلسه از قبل ثبت شده ⇒ مالی همان کلاس تغییر کرده است.
                        invalidateClassCaches(item.courseId)
                        QueueSendResult.ALREADY_REGISTERED
                    } else {
                        val serverMsg = try {
                            e.response()?.errorBody()?.string()?.let { body ->
                                (org.json.JSONObject(body).opt("detail") as? String)?.takeIf { it.isNotBlank() }
                            }
                        } catch (parseErr: Exception) { null }
                        PendingAttendanceStore.updateStatus(
                            this, item.id,
                            PendingAttendanceStore.Status.FAILED,
                            getString(R.string.attendance_http_error, e.code(), serverMsg ?: getString(R.string.attendance_invalid_response))
                        )
                        QueueSendResult.FAILED
                    }
                }
                else -> {
                    PendingAttendanceStore.updateStatus(
                        this, item.id,
                        PendingAttendanceStore.Status.FAILED,
                        e.message ?: getString(R.string.common_unknown_error)
                    )
                    QueueSendResult.FAILED
                }
            }
        }
    }

    /**
     * FIX C10-B3: manual retry of ONE failed item (FAILED = server error, needs human attention).
     * Never retries the whole queue.
     */
    private fun retryQueueItem(itemId: String) {
        if (!isNetworkAvailable()) {
            Toast.makeText(this, getString(R.string.attendance_offline_retry), Toast.LENGTH_SHORT).show()
            return
        }
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val item = PendingAttendanceStore.getAll(this@AttendanceActivity).find { it.id == itemId }
                    ?: return@launch
                val result = sendQueueItem(item)
                withContext(Dispatchers.Main) {
                    when (result) {
                        QueueSendResult.SENT ->
                            Toast.makeText(this@AttendanceActivity, getString(R.string.attendance_submit_ok), Toast.LENGTH_SHORT).show()
                        QueueSendResult.ALREADY_REGISTERED ->
                            Toast.makeText(this@AttendanceActivity, getString(R.string.attendance_submit_dup), Toast.LENGTH_LONG).show()
                        QueueSendResult.NETWORK_DOWN ->
                            Toast.makeText(this@AttendanceActivity, getString(R.string.attendance_submit_netdown), Toast.LENGTH_SHORT).show()
                        QueueSendResult.FAILED -> {
                            val err = PendingAttendanceStore.getAll(this@AttendanceActivity)
                                .find { it.id == itemId }?.lastError ?: getString(R.string.error_server)
                            Toast.makeText(this@AttendanceActivity, getString(R.string.attendance_send_failed, err), Toast.LENGTH_LONG).show()
                        }
                    }
                    refreshQueueCard()
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e
                // Any surprise here leaves the store untouched; the card still shows the item.
            }
        }
    }

    /**
     * FIX C10-B3: re-renders the offline-queue card. Safe to call from any thread.
     * Hidden (gone) when the queue is empty.
     */
    private fun refreshQueueCard() {
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            val items = PendingAttendanceStore.getAll(this@AttendanceActivity)
            withContext(Dispatchers.Main) {
                val card = findViewById<View>(R.id.cardQueueStatus)
                val title = findViewById<TextView>(R.id.tvQueueTitle)
                val list = findViewById<ViewGroup>(R.id.llQueueItems)
                list.removeAllViews()
                if (items.isEmpty()) {
                    card.visibility = View.GONE
                    return@withContext
                }
                card.visibility = View.VISIBLE
                title.text = getString(R.string.attendance_queue_title, items.size)
                for (item in items) {
                    val chip = when (item.status) {
                        PendingAttendanceStore.Status.PENDING -> getString(R.string.attendance_status_pending)
                        PendingAttendanceStore.Status.SENDING -> getString(R.string.attendance_status_sending)
                        PendingAttendanceStore.Status.FAILED -> getString(R.string.attendance_queue_failed_label, item.lastError ?: getString(R.string.error_server))
                    }
                    val row = android.widget.LinearLayout(this@AttendanceActivity).apply {
                        orientation = android.widget.LinearLayout.HORIZONTAL
                        gravity = android.view.Gravity.CENTER_VERTICAL
                    }
                    val label = TextView(this@AttendanceActivity).apply {
                        layoutParams = android.widget.LinearLayout.LayoutParams(
                            0, android.widget.LinearLayout.LayoutParams.WRAP_CONTENT, 1f
                        )
                        textSize = 12f
                        val kind = if (item.op == PendingAttendanceStore.Op.EDIT) getString(R.string.attendance_op_edit) else getString(R.string.attendance_op_submit)
                        val where = item.className?.takeIf { it.isNotBlank() } ?: getString(R.string.attendance_class_fallback, item.courseId)
                        text = getString(R.string.attendance_queue_row, kind, where, item.date, chip)
                    }
                    row.addView(label)
                    if (item.status == PendingAttendanceStore.Status.FAILED) {
                        val retry = MaterialButton(this@AttendanceActivity).apply {
                            text = getString(R.string.btn_retry)
                            textSize = 11f
                            isAllCaps = false
                            minimumWidth = 0
                            setOnClickListener { retryQueueItem(item.id) }
                        }
                        row.addView(retry)
                    }
                    list.addView(row)
                }
            }
        }
    }

    private fun isNetworkAvailable(): Boolean {
        val cm = getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val network = cm.activeNetwork ?: return false
        val caps = cm.getNetworkCapabilities(network) ?: return false
        return caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
    }

    private fun refreshNetworkStatus() {
        if (isNetworkAvailable()) {
            tvNetworkStatus.text = getString(R.string.attendance_net_online)
            tvNetworkStatus.setBackgroundColor(UiColors.resolve(this@AttendanceActivity, R.color.gaj_green_dark))
        } else {
            tvNetworkStatus.text = getString(R.string.attendance_net_offline)
            tvNetworkStatus.setBackgroundColor(UiColors.resolve(this@AttendanceActivity, R.color.gaj_red_error))
        }
    }

    private fun loadSessionDetailsForEdit() {
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            // مرحله‌ی ۱: پیدا کردن خودِ جلسه — اگر جلسه نباشد اصلاً سراغ کلاس نمی‌رویم.
            val details: SessionDetailsResponse = try {
                apiSubmit.getSessionDetails(targetSessionCode)
            } catch (e: Exception) {
                if (e is kotlinx.coroutines.CancellationException) throw e
                Log.e("AttendanceActivity", "loadSessionDetailsForEdit: session lookup failed (code=$targetSessionCode)", e)
                withContext(Dispatchers.Main) {
                    val msg = if (e is HttpException && e.code() == 404) getString(R.string.attendance_session_not_found) else describeApiError(e)
                    Toast.makeText(this@AttendanceActivity, msg, Toast.LENGTH_LONG).show()
                    if (!isFinishing) finish()
                }
                return@launch
            }

            classId = details.course_id
            editSessionDate = details.date // FIX (audit-v2/#13): حفظ تاریخ اصلی جلسه برای پس‌فرستادن

            // FIX(null-class): کلاس جلسه باید قبل از هر درخواست معتبر باشد.
            if (classId <= 0) {
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@AttendanceActivity, getString(R.string.attendance_class_deleted), Toast.LENGTH_LONG).show()
                    if (!isFinishing) finish()
                }
                return@launch
            }

            // مرحله‌ی ۲: لود و نمایش لیست دانش‌آموزان از روی کلاس متناظر
            try {
                val classResponse = apiDetails.getClassDetails(classId)
                studentList = classResponse.students

                // پر کردن وضعیت حضور غیاب‌های قدیمی
                details.items.forEach { item ->
                    attendanceMap.putIfAbsent(item.student_id, item.status)
                    excusedMap.putIfAbsent(item.student_id, item.excused)
                }

                withContext(Dispatchers.Main) {
                    findViewById<TextView>(R.id.tvPageTitle).text = getString(R.string.attendance_edit_loaded, details.session_code, details.class_title)
                    findViewById<TextView>(R.id.etSessionDate).text = details.date // FIX (audit-v2/#13): نمایش تاریخ اصلی جلسه
                    rv.adapter = AttendanceAdapter(studentList, attendanceMap, excusedMap)
                }
            } catch (e: Exception) {
                if (e is kotlinx.coroutines.CancellationException) throw e
                // FIX(null-class): پیام مشخص برای کلاس حذف‌شده + لاگ کامل خطا.
                Log.e("AttendanceActivity", "loadSessionDetailsForEdit: class details failed (classId=$classId)", e)
                withContext(Dispatchers.Main) {
                    val msg = if (e is HttpException && e.code() == 404) getString(R.string.attendance_class_deleted) else describeApiError(e)
                    Toast.makeText(this@AttendanceActivity, msg, Toast.LENGTH_LONG).show()
                    if (!isFinishing) finish()
                }
            }
        }
    }

    private fun fetchStudents() {
        // FIX(null-class): classId=-1/0 هرگز به سرور فرستاده نمی‌شود (جلوگیری از GET /classes/-1/details).
        if (classId <= 0) {
            showClassPickerDialog()
            return
        }
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                // دریافت لیست دانش‌آموزان از API جزئیات کلاس
                val response = apiDetails.getClassDetails(classId)
                studentList = response.students

                // پیش‌فرض همه حاضر و غیرموجه (putIfAbsent: مقادیر بازیابی‌شده از چرخش گوشی حفظ شود)
                studentList.forEach {
                    attendanceMap.putIfAbsent(it.student_id, "Present")
                    excusedMap.putIfAbsent(it.student_id, false)
                }

                withContext(Dispatchers.Main) {
                    rv.adapter = AttendanceAdapter(studentList, attendanceMap, excusedMap)
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                // FIX(null-class): لاگ کامل (با stack trace) + پیام تفکیک‌شده بر اساس نوع خطا.
                Log.e("AttendanceActivity", "fetchStudents failed (classId=$classId)", e)
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@AttendanceActivity, describeApiError(e), Toast.LENGTH_LONG).show()
                    // خطای قطعی (ناموجود/بدون‌دسترسی/منقضی‌شده): ماندن روی صفحه‌ی خالی معنا ندارد.
                    if (e is HttpException && e.code() in setOf(401, 403, 404) && !isFinishing) finish()
                }
            }
        }
    }

    // FIX(null-class): تفکیک انواع خطا و نمایش پیام قابل فهم (401/403/404/5xx/شبکه).
    private fun describeApiError(e: Throwable): String {
        return when (e) {
            is HttpException -> {
                val detail = e.response()?.errorBody()?.string()?.let { body ->
                    try {
                        val value = org.json.JSONObject(body).optString("detail")
                        value.ifBlank { null }
                    } catch (ignored: Exception) { null }
                }
                when (e.code()) {
                    401 -> getString(R.string.attendance_unauthorized)
                    403 -> getString(R.string.attendance_no_permission)
                    404 -> detail ?: getString(R.string.attendance_not_found)
                    else -> getString(R.string.attendance_server_error, e.code(), detail ?: "")
                }
            }
            is IOException -> getString(R.string.attendance_network_error)
            else -> getString(R.string.attendance_class_list_error)
        }
    }

    // FIX(null-class): انتخابگر کلاس — ورود از منوی اصلی بدون کلاس؛ کلاس معتبر قبل از هر درخواست انتخاب می‌شود.
    private fun showClassPickerDialog() {
        val loading = AlertDialog.Builder(this)
            .setTitle(R.string.attendance_select_class_title)
            .setMessage(R.string.attendance_class_missing)
            .setCancelable(false)
            .show()
        lifecycleScope.launch(Dispatchers.IO) {
            val classes = try {
                classApi.getAllClasses()
            } catch (e: Throwable) {
                if (e is kotlinx.coroutines.CancellationException) throw e
                Log.e("AttendanceActivity", "showClassPickerDialog: class list load failed", e)
                withContext(Dispatchers.Main) {
                    loading.dismiss()
                    if (!isFinishing) {
                        Toast.makeText(this@AttendanceActivity, describeApiError(e), Toast.LENGTH_LONG).show()
                        finish()
                    }
                }
                return@launch
            }
            withContext(Dispatchers.Main) {
                loading.dismiss()
                if (isFinishing || isDestroyed) return@withContext
                if (classes.isEmpty()) {
                    Toast.makeText(this@AttendanceActivity, getString(R.string.attendance_classes_empty), Toast.LENGTH_LONG).show()
                    finish()
                    return@withContext
                }
                try {
                    val labels = classes.map { c ->
                        val title = c.title.ifBlank { getString(R.string.attendance_class_without_title) }
                        title + " (" + c.code.ifBlank { "-" } + ")"
                    }
                    AlertDialog.Builder(this@AttendanceActivity)
                        .setTitle(R.string.attendance_select_class_title)
                        .setItems(labels.toTypedArray()) { _, which ->
                            classId = classes[which].id
                            findViewById<TextView>(R.id.tvPageTitle).text = getString(
                                R.string.attendance_title_class,
                                classes[which].title.ifBlank { getString(R.string.attendance_class_without_title) }
                            )
                            fetchStudents()
                        }
                        .setNegativeButton(R.string.btn_dismiss) { _, _ -> if (!isFinishing) finish() }
                        .show()
                } catch (e: Exception) {
                    // تله‌ی نهایی: داده‌ی غیرمنتظره‌ی فهرست کلاس نباید اپ را crash کند.
                    Log.e("AttendanceActivity", "showClassPickerDialog: rendering class list failed", e)
                    Toast.makeText(this@AttendanceActivity, getString(R.string.attendance_class_list_error), Toast.LENGTH_LONG).show()
                    if (!isFinishing) finish()
                }
            }
        }
    }

    private fun promptConfirmSession() {
        val titleText = if (mode == "EDIT_SESSION") getString(R.string.attendance_confirm_edit_title) else getString(R.string.attendance_confirm_submit_title)
        val messageText = if (mode == "EDIT_SESSION") getString(R.string.attendance_confirm_edit_msg) else getString(R.string.attendance_confirm_submit_msg)

        val dialog = AlertDialog.Builder(this)
            .setTitle(titleText)
            .setMessage(messageText)
            .setPositiveButton(getString(R.string.common_yes)) { _, _ -> submitSession() }
            .setNegativeButton(getString(R.string.common_no), null)
            .create()

        dialog.show()
        dialog.getButton(AlertDialog.BUTTON_POSITIVE).setTextColor(UiColors.resolve(this@AttendanceActivity, R.color.status_success))
        dialog.getButton(AlertDialog.BUTTON_NEGATIVE).setTextColor(UiColors.resolve(this@AttendanceActivity, R.color.status_danger))
    }

    private fun submitSession() {
        if (studentList.isEmpty()) return

        // بسته‌بندی اطلاعات حضور و غیاب مجهز به فیلد موجه/غیرموجه بودن غیبت
        val items = studentList.map { student ->
            val status = attendanceMap[student.student_id] ?: "Present"
            val excused = excusedMap[student.student_id] ?: false
            SessionItem(student.student_id, status, excused)
        }

        // FIX (audit-v2/#13): ثبت → امروزِ شمسی (JalaliUtils)؛ ویرایش → تاریخ اصلی جلسه (قبلاً امروزِ میلادی برای هر دو بود).
        val date = if (mode == "EDIT_SESSION") (editSessionDate ?: JalaliUtils.todayJalaliString()) else JalaliUtils.todayJalaliString()
        val data = SessionSubmitData(classId, date, items)

        // بررسی واقعی اتصال: بدون شبکه اجازه‌ی ثبت نده؛ اطلاعات روی صفحه می‌ماند تا وصل شود.
        refreshNetworkStatus()
        if (!isNetworkAvailable()) {
            Toast.makeText(this, getString(R.string.attendance_offline_kept), Toast.LENGTH_LONG).show()
            return
        }

        executeSessionSubmissionOnServer(data)
    }

    private fun executeSessionSubmissionOnServer(data: SessionSubmitData) {
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val res = if (mode == "EDIT_SESSION") {
                    apiSubmit.editSession(targetSessionCode, data)
                } else {
                    apiSubmit.submitSession(data)
                }
                // FIX (کلاس-مالی/تازگی): بعد از ثبت/ویرایش موفق جلسه، snapshot قبل از جلسهٔ صفحهٔ کلاس
                // بی‌اعتبار شود؛ وگرنه بازگشت به صفحهٔ کلاس (یا حالت آفلاین با کش ≤۵ دقیقه) همان
                // «درآمد وصول شده / بدهی به معلم / بدهی به آموزشگاه» قدیمی — مثلاً صفر — را نشان می‌داد.
                invalidateClassCaches(data.course_id)
                withContext(Dispatchers.Main) {
                    showAttendancePrintDialog(res)
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                // FIX C10-B1: split network failures from real server errors (was one generic message).
                // NOTE: runs on Dispatchers.IO, so reading errorBody here is safe.
                val userMessage = when (e) {
                    is java.io.IOException -> {
                        // Network cut (UnknownHost/SocketTimeout/Connect) — NOT a server rejection.
                        // FIX C10-B2: persist into the durable queue (TODO resolved) — survives rotation/process death.
                        val queued = try {
                            PendingAttendanceStore.add(
                                this@AttendanceActivity,
                                PendingAttendanceStore.PendingItem(
                                    op = if (mode == "EDIT_SESSION") PendingAttendanceStore.Op.EDIT else PendingAttendanceStore.Op.SUBMIT,
                                    targetSessionCode = targetSessionCode.takeIf { mode == "EDIT_SESSION" && it != -1 },
                                    courseId = classId,
                                    className = intent.getStringExtra("TARGET_COURSE_NAME"),
                                    date = data.date,
                                    items = data.items.map { PendingAttendanceStore.PendingStudent(it.student_id, it.status, it.excused) }
                                )
                            )
                            true
                        } catch (storeErr: Exception) { false }
                        // FIX C10-B3: re-render the card so the new item shows immediately.
                        refreshQueueCard()
                        if (queued) getString(R.string.attendance_queued_ok)
                        else getString(R.string.attendance_queue_save_failed)
                    }
                    is retrofit2.HttpException -> {
                        val serverMsg = try {
                            e.response()?.errorBody()?.string()?.let { body ->
                                (org.json.JSONObject(body).opt("detail") as? String)?.takeIf { it.isNotBlank() }
                            }
                        } catch (parseErr: Exception) { null }
                        when (e.code()) {
                            409 -> getString(R.string.common_err_with_detail, serverMsg ?: getString(R.string.attendance_already_registered))
                            400, 404, 422 -> getString(R.string.common_err_with_detail, serverMsg ?: getString(R.string.attendance_validation_check))
                            in 500..599 -> getString(R.string.attendance_server_error_retry, e.code())
                            else -> getString(R.string.attendance_http_fallback, e.code(), serverMsg ?: getString(R.string.common_retry_later))
                        }
                    }
                    else -> getString(R.string.attendance_submit_failed, e.message ?: getString(R.string.common_unknown_error))
                }
                withContext(Dispatchers.Main) {
                    refreshNetworkStatus()
                    Toast.makeText(this@AttendanceActivity, userMessage, Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    private fun showAttendancePrintDialog(res: SessionResponse) {
        val retrofit = RetrofitClient.getInstance(this)
        val detailsApi = retrofit.create(ClassDetailApi::class.java)
        val settingsApi = retrofit.create(InstituteSettingsApi::class.java)
        
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val fullReport = detailsApi.getClassReport(classId)
                val studentsFull = detailsApi.getClassStudentsFull(classId)
                val settings = settingsApi.getSettings()

                withContext(Dispatchers.Main) {
                    val codeVal = res.session_code ?: 100001
                    val instAddress = settings.address
                    val instPhone = settings.phone
                    val instFooter = settings.footer_text ?: getString(R.string.common_thanks)
                    
                    val teacherName = fullReport.info.teacher_name
                    val classCode = fullReport.info.code
                    
                    val totalDebtTeacher = studentsFull.students.sumOf { it.debt_teacher }
                    val totalDebtInstitute = studentsFull.students.sumOf { it.debt_institute }
                    val totalPaidTeacher = studentsFull.students.sumOf { it.paid_teacher }
                    val totalPaidInstitute = studentsFull.students.sumOf { it.paid_institute }

                    // ساخت قالب HTML فیش حضور و غیاب باریک (عرض ۸۰ میلی‌متر)
                    val webView = android.webkit.WebView(this@AttendanceActivity)
                    
                    val studentRows = studentsFull.students.mapIndexed { index, student ->
                        val paidTeacher = student.paid_teacher
                        val paidInstitute = student.paid_institute
                        val debtTeacher = student.debt_teacher
                        val debtInstitute = student.debt_institute

                        """
                        <tr>
                            <td>${index + 1}. ${student.student_name}</td>
                            <td>${String.format("%,d", debtTeacher)} / ${String.format("%,d", debtInstitute)}</td>
                            <td>${String.format("%,d", paidTeacher)} / ${String.format("%,d", paidInstitute)}</td>
                        </tr>
                        """
                    }.joinToString("")

                    val htmlContent = """
                        <html>
                        <head>
                            <style>
                                body { width: 80mm; font-family: Tahoma, sans-serif; direction: rtl; padding: 10px; margin: 0; font-size: 11px; }
                                .header { text-align: center; border-bottom: 1px dashed #333; padding-bottom: 8px; margin-bottom: 15px; }
                                .title { font-size: 13px; font-weight: bold; }
                                .row { margin-bottom: 5px; font-size: 11px; }
                                .label { font-weight: bold; }
                                .footer { margin-top: 15px; text-align: center; font-size: 9px; color: #555; border-top: 1px dashed #333; padding-top: 6px; }
                                table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 9px; }
                                th, td { border: 1px solid #ddd; padding: 4px; text-align: center; }
                                th { background-color: #f5f5f5; }
                            </style>
                        </head>
                        <body>
                            <div class="header">
                                <div class="title">${getString(R.string.attendance_html_title)}</div>
                                <div style="font-size: 9px; margin-top: 4px;">${getString(R.string.attendance_html_contact, instAddress, instPhone)}</div>
                                <div style="font-size: 10px; font-weight: bold; margin-top: 6px;">${getString(R.string.attendance_html_doc, codeVal)}</div>
                            </div>

                            <div style="padding: 5px;">
                                <div class="row"><span class="label">${getString(R.string.attendance_lbl_teacher)}</span> $teacherName</div>
                                <div class="row"><span class="label">${getString(R.string.attendance_lbl_class)}</span> $classCode</div>
                                <div class="row"><span class="label">${getString(R.string.attendance_lbl_present)}</span> ${res.details?.present_count ?: 0} ${getString(R.string.attendance_present_suffix)}</div>
                                <div class="row"><span class="label">${getString(R.string.attendance_lbl_debt)}</span> ${String.format("%,d", totalDebtTeacher)} / ${String.format("%,d", totalDebtInstitute)} ${getString(R.string.attendance_toman)}</div>
                                <div class="row"><span class="label">${getString(R.string.attendance_lbl_paid)}</span> ${String.format("%,d", totalPaidTeacher)} / ${String.format("%,d", totalPaidInstitute)} ${getString(R.string.attendance_toman)}</div>
                                
                                <table>
                                    <thead>
                                        <tr>
                                            <th>${getString(R.string.classes_students)}</th>
                                            <th>${getString(R.string.attendance_th_debt)}</th>
                                            <th>${getString(R.string.attendance_th_paid)}</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        $studentRows
                                    </tbody>
                                </table>
                            </div>

                            <div class="footer">
                                $instFooter
                            </div>
                        </body>
                        </html>
                    """.trimIndent()

                    val dialogView = LayoutInflater.from(this@AttendanceActivity).inflate(R.layout.dialog_remittance_success, null)
                    
                    val imgSuccessIcon = dialogView.findViewById<ImageView>(R.id.imgSuccessIcon)
                    if (imgSuccessIcon != null) {
                        imgSuccessIcon.alpha = 0f
                        imgSuccessIcon.scaleX = 0f
                        imgSuccessIcon.scaleY = 0f
                        imgSuccessIcon.animate()
                            .alpha(1f)
                            .scaleX(1f)
                            .scaleY(1f)
                            .setDuration(AnimationConstants.ANIM_TRANSITION)
                            .setInterpolator(android.view.animation.OvershootInterpolator())
                            .start()
                    }

                    val dialog = AlertDialog.Builder(this@AttendanceActivity)
                        .setView(dialogView)
                        .setCancelable(false)
                        .create()

                    dialogView.findViewById<TextView>(R.id.tvSuccessMessage).text = 
                        getString(R.string.attendance_receipt_ok, codeVal, String.format("%,d", res.details?.teacher_share ?: 0), String.format("%,d", res.details?.institute_share ?: 0))
                    dialogView.findViewById<TextView>(R.id.tvSuccessMessage).gravity = android.view.Gravity.CENTER

                    // دکمه ثبت مجدد نیازی نیست
                    dialogView.findViewById<com.google.android.material.button.MaterialButton>(R.id.btnRegisterAgain).visibility = View.GONE

                    val btnPrint = dialogView.findViewById<com.google.android.material.button.MaterialButton>(R.id.btnPrintRemittance)
                    btnPrint.text = getString(R.string.attendance_print_receipt)
                    btnPrint.setOnClickListener {
                        webView.loadDataWithBaseURL(null, htmlContent, "text/html", "UTF-8", null)
                        val printManager = getSystemService(android.content.Context.PRINT_SERVICE) as android.print.PrintManager
                        val printAdapter = webView.createPrintDocumentAdapter("Attendance_Session_$codeVal")
                        printManager.print("Kharazmi_Attendance_Session_$codeVal", printAdapter, android.print.PrintAttributes.Builder().build())
                    }

                    val btnSavePdf = dialogView.findViewById<com.google.android.material.button.MaterialButton>(R.id.btnSaveAsPdf)
                    btnSavePdf.text = getString(R.string.attendance_save_pdf)
                    btnSavePdf.setOnClickListener {
                        val pdfDocument = android.graphics.pdf.PdfDocument()
                        val pageInfo = android.graphics.pdf.PdfDocument.PageInfo.Builder(280, 500, 1).create()
                        val page = pdfDocument.startPage(pageInfo)
                        val canvas = page.canvas
                        val paint = android.graphics.Paint()

                        canvas.drawColor(android.graphics.Color.WHITE)
                        paint.color = android.graphics.Color.BLACK
                        paint.textSize = 12f
                        paint.textAlign = android.graphics.Paint.Align.CENTER
                        canvas.drawText(getString(R.string.attendance_pdf_title), 280f / 2, 30f, paint)

                        paint.textSize = 8f
                        canvas.drawText(getString(R.string.attendance_pdf_teacher, teacherName, classCode), 280f / 2, 50f, paint)
                        canvas.drawText(getString(R.string.attendance_pdf_session, codeVal), 280f / 2, 65f, paint)

                        canvas.drawLine(10f, 75f, 270f, 75f, paint)

                        paint.textSize = 9f
                        paint.textAlign = android.graphics.Paint.Align.RIGHT
                        var startY = 100f
                        val lineHeight = 20f

                        canvas.drawText(getString(R.string.attendance_pdf_debt, String.format("%,d", totalDebtTeacher), String.format("%,d", totalDebtInstitute)), 260f, startY, paint)
                        startY += lineHeight
                        canvas.drawText(getString(R.string.attendance_pdf_paid, String.format("%,d", totalPaidTeacher), String.format("%,d", totalPaidInstitute)), 260f, startY, paint)
                        
                        startY += 15f
                        canvas.drawText(getString(R.string.attendance_pdf_list), 260f, startY, paint)
                        startY += 15f

                        paint.textSize = 8f
                        studentsFull.students.forEach { s ->
                            val debtT = s.debt_teacher
                            val debtI = s.debt_institute
                            canvas.drawText(getString(R.string.attendance_pdf_row, s.student_name, debtT, debtI, s.paid_teacher, s.paid_institute), 260f, startY, paint)
                            startY += 15f
                        }

                        canvas.drawLine(10f, startY + 10f, 270f, startY + 10f, paint)
                        paint.color = android.graphics.Color.BLACK
                        paint.textAlign = android.graphics.Paint.Align.CENTER
                        canvas.drawText(instFooter, 280f / 2, startY + 30f, paint)

                        pdfDocument.finishPage(page)

                        val fileName = "Attendance_Session_$codeVal.pdf"
                        val file = java.io.File(android.os.Environment.getExternalStoragePublicDirectory(android.os.Environment.DIRECTORY_DOWNLOADS), fileName)
                        try {
                            pdfDocument.writeTo(java.io.FileOutputStream(file))
                            Toast.makeText(this@AttendanceActivity, getString(R.string.attendance_pdf_saved, fileName), Toast.LENGTH_LONG).show()
                        } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                            Toast.makeText(this@AttendanceActivity, getString(R.string.attendance_pdf_error, e.message), Toast.LENGTH_LONG).show()
                        } finally {
                            pdfDocument.close()
                        }
                    }

                    val btnClose = dialogView.findViewById<com.google.android.material.button.MaterialButton>(R.id.btnClose)
                    btnClose.setOnClickListener {
                        dialog.dismiss()
                        finish()
                    }

                    dialog.show()
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                android.util.Log.e("AttendanceActivity", "showAttendancePrintDialog failed", e)
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@AttendanceActivity, getString(R.string.attendance_receipt_error), Toast.LENGTH_SHORT).show()
                    finish()
                }
            }
        }
    }
}

// آداپتور حضور و غیاب ارتقا یافته
class AttendanceAdapter(
    private val list: List<StudentItem>,
    private val map: HashMap<Int, String>,
    private val excusedMap: HashMap<Int, Boolean>
) : RecyclerView.Adapter<AttendanceAdapter.VH>() {

    class VH(v: View) : RecyclerView.ViewHolder(v) {
        val name: TextView = v.findViewById(R.id.tvStName)
        val rg: RadioGroup = v.findViewById(R.id.rgStatus)
        val rgAbsenceType: RadioGroup = v.findViewById(R.id.rgAbsenceType)
        val rbUnexcused: RadioButton = v.findViewById(R.id.rbUnexcused)
        val rbExcused: RadioButton = v.findViewById(R.id.rbExcused)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val v = LayoutInflater.from(parent.context).inflate(R.layout.item_attendance, parent, false)
        return VH(v)
    }

    override fun onBindViewHolder(holder: VH, position: Int) {
        val item = list[position]
        holder.name.text = item.student_name

        // کلیک روی نام برای باز کردن پروفایل
        holder.name.setOnClickListener {
            val intent = Intent(holder.itemView.context, StudentProfileActivity::class.java)
            intent.putExtra("STUDENT_ID", item.student_id)
            holder.itemView.context.startActivity(intent)
        }

        holder.rg.setOnCheckedChangeListener(null)
        holder.rgAbsenceType.setOnCheckedChangeListener(null)

        // بازگرداندن وضعیت قبلی رادیوباتن‌ها
        when (map[item.student_id]) {
            "Present" -> {
                holder.rg.check(R.id.rbPresent)
                holder.rgAbsenceType.visibility = View.GONE
            }
            "Absent" -> {
                holder.rg.check(R.id.rbAbsent)
                holder.rgAbsenceType.visibility = View.VISIBLE
                if (excusedMap[item.student_id] == true) {
                    holder.rgAbsenceType.check(R.id.rbExcused)
                } else {
                    holder.rgAbsenceType.check(R.id.rbUnexcused)
                }
            }
            "Late" -> {
                holder.rg.check(R.id.rbLate)
                holder.rgAbsenceType.visibility = View.GONE
            }
        }

        // گوش دادن به تغییر وضعیت حضور غیاب
        holder.rg.setOnCheckedChangeListener { _, checkedId ->
            val status = when (checkedId) {
                R.id.rbPresent -> "Present"
                R.id.rbAbsent -> "Absent"
                else -> "Late"
            }
            map[item.student_id] = status
            
            if (status == "Absent") {
                holder.rgAbsenceType.visibility = View.VISIBLE
                // پیش‌فرض غیرموجه
                excusedMap[item.student_id] = holder.rbExcused.isChecked
            } else {
                holder.rgAbsenceType.visibility = View.GONE
                excusedMap[item.student_id] = false
            }
        }

        // گوش دادن به تغییر وضعیت موجه/غیرموجه بودن غیبت
        holder.rgAbsenceType.setOnCheckedChangeListener { _, checkedId ->
            val isExcused = checkedId == R.id.rbExcused
            excusedMap[item.student_id] = isExcused
        }
    }

    override fun getItemCount() = list.size
}
