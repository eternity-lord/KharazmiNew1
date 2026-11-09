package com.example.kharazmiadmin

import android.content.Intent
import android.graphics.Color
import android.os.Bundle
import android.text.Editable
import android.text.TextWatcher
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.ProgressBar
import android.widget.TextView
import android.widget.Toast
import androidx.core.graphics.ColorUtils
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.google.android.material.button.MaterialButton
import com.google.android.material.textfield.TextInputEditText
import ir.hamsaa.persiandatepicker.PersianDatePickerDialog
import ir.hamsaa.persiandatepicker.util.PersianCalendar
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.util.Locale

/**
 * «کلاس‌های حذفی (آرشیو ادمین)» — صفحهٔ مستقل (قبلاً یک AlertDialog ساده بود).
 *
 * - فهرست کلاس‌های حذف‌شده با کارت‌های رنگی؛ لمس هر کارت ⇒ گزارش کامل کلاس (ArchivedClassDetailActivity).
 * - جست‌وجوی زنده (با مکث ۲۵۰ms): نام کلاس، نام معلم، کد کلاس و بازهٔ تاریخ حذف (جلالی).
 * - فقط GET /admin/deleted_classes مصرف می‌شود؛ هیچ داده‌ای اینجا تغییر نمی‌کند.
 */
class ArchivedClassesActivity : BaseActivity() {

    private lateinit var rv: RecyclerView
    private lateinit var tvSubtitle: TextView
    private lateinit var tvEmpty: TextView
    private lateinit var progress: ProgressBar
    private lateinit var etTitle: TextInputEditText
    private lateinit var etCode: TextInputEditText
    private lateinit var etTeacher: TextInputEditText
    private lateinit var btnFrom: MaterialButton
    private lateinit var btnTo: MaterialButton
    private lateinit var btnClear: MaterialButton
    private lateinit var btnBack: MaterialButton

    private lateinit var api: DeletedClassesApi
    private val items = mutableListOf<ArchivedClassItem>()
    private lateinit var adapter: ArchivedClassAdapter

    private var fromDate: String? = null   // yyyy/MM/dd جلالی
    private var toDate: String? = null
    private var searchJob: Job? = null
    private var loadJob: Job? = null
    private var requestSeq = 0

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_archived_classes)

        rv = findViewById(R.id.rvArchivedClasses)
        tvSubtitle = findViewById(R.id.tvArchiveSubtitle)
        tvEmpty = findViewById(R.id.tvArchiveEmpty)
        progress = findViewById(R.id.progressArchive)
        etTitle = findViewById(R.id.etArchiveTitle)
        etCode = findViewById(R.id.etArchiveCode)
        etTeacher = findViewById(R.id.etArchiveTeacher)
        btnFrom = findViewById(R.id.btnArchiveFrom)
        btnTo = findViewById(R.id.btnArchiveTo)
        btnClear = findViewById(R.id.btnArchiveClear)
        btnBack = findViewById(R.id.btnArchiveBack)

        api = RetrofitClient.getInstance(this).create(DeletedClassesApi::class.java)
        adapter = ArchivedClassAdapter(items) { item ->
            startActivity(Intent(this, ArchivedClassDetailActivity::class.java).putExtra(ArchivedClassDetailActivity.EXTRA_COURSE_ID, item.id))
        }
        rv.layoutManager = LinearLayoutManager(this)
        rv.adapter = adapter

        btnBack.setOnClickListener { finish() }
        val watcher = object : TextWatcher {
            override fun afterTextChanged(s: Editable?) { scheduleSearch() }
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {}
        }
        etTitle.addTextChangedListener(watcher)
        etCode.addTextChangedListener(watcher)
        etTeacher.addTextChangedListener(watcher)
        btnFrom.setOnClickListener { pickDate(isFrom = true) }
        btnTo.setOnClickListener { pickDate(isFrom = false) }
        btnClear.setOnClickListener {
            fromDate = null
            toDate = null
            // پاک‌کردن متن‌ها watcher را صدا می‌زند؛ جست‌وجوی نهایی یک‌بار با scheduleSearch انجام می‌شود.
            etTitle.setText("")
            etCode.setText("")
            etTeacher.setText("")
            searchJob?.cancel()   // جست‌وجوی زمان‌بندی‌شدهٔ watcherها؛ پایین یک load فوری داریم
            updateDateLabels()
            updateClearVisibility()
            load()
        }
        updateDateLabels()
    }

    override fun onResume() {
        super.onResume()
        // بازگشت از صفحهٔ جزئیات (مثلاً بعد از «بازیابی») ⇒ فهرست همیشه تازه است.
        load()
    }

    private fun filterTitle() = etTitle.text?.toString()?.trim()?.takeIf { it.isNotEmpty() }
    private fun filterCode() = etCode.text?.toString()?.trim()?.takeIf { it.isNotEmpty() }
    private fun filterTeacher() = etTeacher.text?.toString()?.trim()?.takeIf { it.isNotEmpty() }
    private fun hasFilters() = filterTitle() != null || filterCode() != null || filterTeacher() != null || fromDate != null || toDate != null

    private fun updateClearVisibility() {
        btnClear.visibility = if (hasFilters()) View.VISIBLE else View.GONE
    }

    private fun updateDateLabels() {
        btnFrom.text = fromDate?.let { getString(R.string.arch_date_from_set, it) } ?: getString(R.string.arch_date_from)
        btnTo.text = toDate?.let { getString(R.string.arch_date_to_set, it) } ?: getString(R.string.arch_date_to)
    }

    /** جست‌وجوی زنده: هر تایپ درخواست قبلی را لغو می‌کند و بعد از مکثِ کوتاه یک درخواست می‌فرستد. */
    private fun scheduleSearch() {
        updateClearVisibility()
        searchJob?.cancel()
        searchJob = lifecycleScope.launch {
            delay(250)
            load()
        }
    }

    private fun load() {
        loadJob?.cancel()
        val seq = ++requestSeq
        progress.visibility = View.VISIBLE
        val title = filterTitle()
        val code = filterCode()
        val teacher = filterTeacher()
        val from = fromDate
        val to = toDate
        val filtered = hasFilters()
        loadJob = lifecycleScope.launch(Dispatchers.IO) {
            try {
                val list = api.getDeletedClasses(title = title, teacher = teacher, code = code, deletedFrom = from, deletedTo = to)
                withContext(Dispatchers.Main) {
                    if (seq != requestSeq) return@withContext   // پاسخ کهنه (کاربر بعدش چیز دیگری تایپ کرد)
                    progress.visibility = View.GONE
                    items.clear()
                    items.addAll(list)
                    adapter.notifyDataSetChanged()
                    tvSubtitle.text = getString(if (filtered) R.string.arch_subtitle_filtered else R.string.arch_subtitle_all, list.size)
                    tvEmpty.text = getString(if (filtered) R.string.arch_empty else R.string.arch_empty_all)
                    tvEmpty.visibility = if (list.isEmpty()) View.VISIBLE else View.GONE
                }
            } catch (e: Exception) {
                if (e is CancellationException) throw e
                withContext(Dispatchers.Main) {
                    if (seq != requestSeq) return@withContext
                    progress.visibility = View.GONE
                    Toast.makeText(this@ArchivedClassesActivity, getString(R.string.arch_error), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    // الگوی PersianDatePickerDialog کانونیکال پروژه (AuditTrailActivity/EditStudentActivity)
    private fun pickDate(isFrom: Boolean) {
        val today = PersianCalendar()
        val parts = (if (isFrom) fromDate else toDate)?.split("/")?.mapNotNull { it.toIntOrNull() }
        val (y, m, d) = if (parts != null && parts.size == 3) Triple(parts[0], parts[1], parts[2])
        else Triple(today.persianYear, today.persianMonth, today.persianDay)

        PersianDatePickerDialog(this)
            .setPositiveButtonString(getString(R.string.arch_pick_ok))
            .setNegativeButton(getString(R.string.arch_pick_cancel))
            .setTodayButton(getString(R.string.arch_pick_today))
            .setTodayButtonVisible(true)
            .setMinYear(1395)
            .setMaxYear(today.persianYear + 1)
            .setInitDate(y, m, d)
            .setActionTextColor(UiColors.resolve(this, R.color.ds_accent))
            .setBackgroundColor(UiColors.resolve(this, R.color.ds_bg_surface))
            .setPickerBackgroundColor(UiColors.resolve(this, R.color.ds_bg_surface_2))
            .setTitleColor(UiColors.resolve(this, R.color.ds_text_primary))
            .setTitleType(PersianDatePickerDialog.WEEKDAY_DAY_MONTH_YEAR)
            .setShowInBottomSheet(true)
            .setListener(object : ir.hamsaa.persiandatepicker.Listener {
                override fun onDateSelected(persianCalendar: PersianCalendar?) {
                    if (persianCalendar == null) return
                    val value = String.format(
                        Locale.US, "%04d/%02d/%02d",
                        persianCalendar.persianYear, persianCalendar.persianMonth, persianCalendar.persianDay
                    )
                    if (isFrom) fromDate = value else toDate = value
                    // تاریخ جلالی صفرپر است ⇒ مقایسهٔ متنی = مقایسهٔ زمانی؛ بازهٔ برعکس جابه‌جا می‌شود
                    val f = fromDate
                    val t = toDate
                    if (f != null && t != null && f > t) {
                        fromDate = t
                        toDate = f
                        Toast.makeText(this@ArchivedClassesActivity, getString(R.string.arch_error_date), Toast.LENGTH_SHORT).show()
                    }
                    updateDateLabels()
                    updateClearVisibility()
                    load()
                }

                override fun onDismissed() {}
            })
            .show()
    }

    // ------------------------------------------------------------------
    // Adapter
    // ------------------------------------------------------------------
    private class ArchivedClassAdapter(
        private val data: List<ArchivedClassItem>,
        private val onClick: (ArchivedClassItem) -> Unit
    ) : RecyclerView.Adapter<ArchivedClassAdapter.Holder>() {

        class Holder(view: View) : RecyclerView.ViewHolder(view) {
            val stripe: View = view.findViewById(R.id.viewArchivedStripe)
            val title: TextView = view.findViewById(R.id.tvArchivedTitle)
            val code: TextView = view.findViewById(R.id.tvArchivedCode)
            val teacher: TextView = view.findViewById(R.id.tvArchivedTeacher)
            val students: TextView = view.findViewById(R.id.tvArchivedStudents)
            val sessions: TextView = view.findViewById(R.id.tvArchivedSessions)
            val forgiven: TextView = view.findViewById(R.id.tvArchivedForgiven)
            val deleted: TextView = view.findViewById(R.id.tvArchivedDeleted)
        }

        override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): Holder =
            Holder(LayoutInflater.from(parent.context).inflate(R.layout.item_archived_class, parent, false))

        override fun getItemCount(): Int = data.size

        override fun onBindViewHolder(holder: Holder, position: Int) {
            val ctx = holder.itemView.context
            val item = data[position]
            // رکورد legacy ممکن است عنوان/معلم/تاریخ نداشته باشد ⇒ هرگز «null» نمایش داده نمی‌شود.
            holder.title.text = item.title?.takeIf { it.isNotBlank() } ?: ctx.getString(R.string.common_unknown_class)
            val code = item.code?.trim().orEmpty()
            holder.code.visibility = if (code.isEmpty()) View.GONE else View.VISIBLE
            holder.code.text = ctx.getString(R.string.arch_row_code, code)
            holder.teacher.text = ctx.getString(
                R.string.arch_row_teacher,
                item.teacherName?.takeIf { it.isNotBlank() } ?: ctx.getString(R.string.common_person_unknown)
            )
            holder.students.text = ctx.getString(R.string.arch_row_students, item.studentsCount)
            holder.sessions.text = ctx.getString(R.string.arch_row_sessions, item.sessionsCount)
            holder.forgiven.text = ctx.getString(R.string.arch_row_forgiven)
            holder.forgiven.visibility = if (item.forgiveSessionCharges) View.VISIBLE else View.GONE
            holder.deleted.text = ArchiveFormat.deletedLine(ctx, item.deletedAtJalali, item.deletedWeekday, item.deletedAt)
            holder.stripe.setBackgroundColor(stripeColor(ctx, item.bgColor))
            holder.itemView.setOnClickListener { onClick(item) }
        }

        /** رنگ خود کلاس؛ اگر نبود/نامعتبر بود یا تقریباً سفید (نامرئی در تم روشن) ⇒ طلایی تم. */
        private fun stripeColor(ctx: android.content.Context, hex: String?): Int {
            val fallback = UiColors.resolve(ctx, R.color.ds_accent)
            val parsed = runCatching { Color.parseColor(hex?.trim().orEmpty()) }.getOrNull() ?: return fallback
            return if (ColorUtils.calculateLuminance(parsed) > 0.9) fallback else parsed
        }
    }
}

/** قالب‌بندی مشترک صفحه‌های آرشیو (فقط نمایش؛ هیچ منطق مالی ندارد). */
object ArchiveFormat {
    /** «حذف: دوشنبه 1405/07/06 07:29»؛ اگر جلالی نبود همان میلادی سرور؛ اگر هیچ‌کدام «تاریخ حذف ثبت نشده». */
    fun deletedLine(ctx: android.content.Context, jalali: String?, weekday: String?, gregorian: String?): String {
        val j = jalali?.trim().orEmpty()
        if (j.isNotEmpty()) return ctx.getString(R.string.arch_row_deleted, weekday?.trim().orEmpty(), j).replace("  ", " ")
        val g = gregorian?.trim().orEmpty()
        if (g.isNotEmpty()) return ctx.getString(R.string.arch_row_deleted, "", g).replace("  ", " ")
        return ctx.getString(R.string.arch_row_deleted_unknown)
    }

    fun money(value: Long): String = String.format(Locale.US, "%,d", value)
}
