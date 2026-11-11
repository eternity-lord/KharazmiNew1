package com.example.kharazmiadmin

import android.content.ActivityNotFoundException
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.AdapterView
import android.widget.ArrayAdapter
import android.widget.ProgressBar
import android.widget.Spinner
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.core.content.FileProvider
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.google.android.material.button.MaterialButton
import com.google.android.material.card.MaterialCardView
import com.google.android.material.textfield.TextInputEditText
import ir.hamsaa.persiandatepicker.PersianDatePickerDialog
import ir.hamsaa.persiandatepicker.util.PersianCalendar
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import java.util.Locale

/**
 * Financial Audit Trail — «چه کسی، چه زمانی، چه چیزی را در داده‌های مالی عوض کرد».
 *
 * - فیلترها: نوع موجودیت، نوع عملیات، شناسه‌ی رکورد، رنج تاریخ (جلالی)
 * - صفحه‌بندی: دکمه‌ی «بارگذاری بیشتر» (سرور حداکثر ۲۰۰ ردیف در هر صفحه می‌دهد)
 * - تپ روی هر ردیف: دیالوگ دیف کامل (قبل/بعد، فقط فیلدهای تغییریافته)
 * - خروجی CSV از همان داده‌ها (بدون هیچ تغییری در سرور)
 *
 * نکته‌ی معماری: هیچ endpoint جدید/تغییری در سرور لازم نشد؛ فقط GET /audit-trail/logs مصرف می‌شود.
 */
class AuditTrailActivity : BaseActivity() {

    private lateinit var rvLogs: RecyclerView
    private lateinit var tvEmpty: TextView
    private lateinit var tvSummary: TextView
    private lateinit var progress: ProgressBar
    private lateinit var btnLoadMore: MaterialButton
    private lateinit var btnRefresh: MaterialButton
    private lateinit var btnClearFilters: MaterialButton
    private lateinit var btnExport: MaterialButton
    private lateinit var btnBack: MaterialButton
    private lateinit var spEntityType: Spinner
    private lateinit var spAction: Spinner
    private lateinit var etEntityId: TextInputEditText
    private lateinit var etSearch: TextInputEditText   // FIX (گروه۲/آیتم۸): جست‌وجوی نام
    private lateinit var btnFromDate: MaterialButton
    private lateinit var btnToDate: MaterialButton

    private lateinit var repository: AuditTrailRepository

    private val logs = mutableListOf<AuditTrailLog>()
    private var adapter: AuditLogAdapter? = null
    private var currentPage = 1
    private var totalPages = 1
    private var totalCount = 0
    private var isLoading = false
    private var fromDate: String? = null   // yyyy/MM/dd جلالی
    private var toDate: String? = null

    /** مقادیر نمایشی Spinner ↔ مقادیر API (index 0 = «همه») */
    private val entityTypeValues = listOf<String?>(null, "transaction", "installment")
    private val actionValues = listOf<String?>(null, "create", "update", "delete")

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_audit_trail)

        initViews()
        setupApi()
        setupSpinners()
        setupListeners()
        loadLogs(reset = true)
    }

    private fun initViews() {
        rvLogs = findViewById(R.id.rvAuditTrail)
        tvEmpty = findViewById(R.id.tvAuditTrailEmpty)
        tvSummary = findViewById(R.id.tvAuditTrailSummary)
        progress = findViewById(R.id.progressAuditTrail)
        btnLoadMore = findViewById(R.id.btnAuditTrailLoadMore)
        btnRefresh = findViewById(R.id.btnAuditTrailRefresh)
        btnClearFilters = findViewById(R.id.btnAuditTrailClear)
        btnExport = findViewById(R.id.btnAuditTrailExport)
        btnBack = findViewById(R.id.btnAuditTrailBack)
        spEntityType = findViewById(R.id.spAuditEntityType)
        spAction = findViewById(R.id.spAuditAction)
        etEntityId = findViewById(R.id.etAuditEntityId)
        etSearch = findViewById(R.id.etAuditSearch)
        btnFromDate = findViewById(R.id.btnAuditFromDate)
        btnToDate = findViewById(R.id.btnAuditToDate)

        rvLogs.layoutManager = LinearLayoutManager(this)
    }

    private fun setupApi() {
        repository = AuditTrailRepository.from(this)
    }

    private fun setupSpinners() {
        val entityLabels = listOf(
            getString(R.string.audit_trail_filter_all),
            getString(R.string.audit_trail_entity_transaction),
            getString(R.string.audit_trail_entity_installment)
        )
        val actionLabels = listOf(
            getString(R.string.audit_trail_filter_all),
            getString(R.string.audit_trail_action_create),
            getString(R.string.audit_trail_action_update),
            getString(R.string.audit_trail_action_delete)
        )
        spEntityType.adapter = ArrayAdapter(this, android.R.layout.simple_spinner_dropdown_item, entityLabels)
        spAction.adapter = ArrayAdapter(this, android.R.layout.simple_spinner_dropdown_item, actionLabels)

        val reload = object : AdapterView.OnItemSelectedListener {
            override fun onItemSelected(parent: AdapterView<*>?, view: View?, position: Int, id: Long) {
                loadLogs(reset = true)
            }

            override fun onNothingSelected(parent: AdapterView<*>?) = Unit
        }
        spEntityType.onItemSelectedListener = reload
        spAction.onItemSelectedListener = reload
    }

    private fun setupListeners() {
        btnBack.setOnClickListener { finish() }
        btnRefresh.setOnClickListener { loadLogs(reset = true) }
        btnLoadMore.setOnClickListener { loadLogs(reset = false) }

        btnClearFilters.setOnClickListener {
            fromDate = null
            toDate = null
            etEntityId.setText("")
            etSearch.setText("")   // FIX (گروه۲/آیتم۸): جست‌وجوی نام هم پاک می‌شود
            updateDateLabels()
            spEntityType.setSelection(0)   // خودِ listener باعث بارگذاری مجدد می‌شود
            spAction.setSelection(0)
            loadLogs(reset = true)
        }

        etEntityId.setOnEditorActionListener { _, _, _ ->
            loadLogs(reset = true)
            true
        }

        etSearch.setOnEditorActionListener { _, _, _ ->
            loadLogs(reset = true)
            true
        }

        btnFromDate.setOnClickListener { pickDate(isFrom = true) }
        btnToDate.setOnClickListener { pickDate(isFrom = false) }

        btnExport.setOnClickListener { exportFilteredLogs() }
    }

    // ------------------------------------------------------------------
    // فیلتر تاریخ — جلالی، هم‌فرمت با سرور (yyyy/MM/dd). سرور خودش جلالی را می‌شناسد.
    // الگوی استفاده از PersianDatePickerDialog عیناً مثل EditStudentActivity (کانونیکال پروژه).
    // ------------------------------------------------------------------
    private fun pickDate(isFrom: Boolean) {
        val today = PersianCalendar()
        val parts = (if (isFrom) fromDate else toDate)?.split("/")?.mapNotNull { it.toIntOrNull() }
        val (initYear, initMonth, initDay) = if (parts != null && parts.size == 3) {
            Triple(parts[0], parts[1], parts[2])
        } else {
            Triple(today.persianYear, today.persianMonth, today.persianDay)
        }

        val picker = PersianDatePickerDialog(this)
            .setPositiveButtonString(getString(R.string.audit_trail_pick_ok))
            .setNegativeButton(getString(R.string.audit_trail_pick_cancel))
            .setTodayButton(getString(R.string.audit_trail_pick_today))
            .setTodayButtonVisible(true)
            .setMinYear(1395)
            .setMaxYear(today.persianYear + 1)
            .setInitDate(initYear, initMonth, initDay)
            .setActionTextColor(UiColors.resolve(this@AuditTrailActivity, R.color.ds_accent))
            // The third-party picker defaults both the sheet and NumberPickers to white.
            // Supply adaptive tokens so Jalali numbers remain visible in night mode.
            .setBackgroundColor(UiColors.resolve(this@AuditTrailActivity, R.color.ds_bg_surface))
            .setPickerBackgroundColor(UiColors.resolve(this@AuditTrailActivity, R.color.ds_bg_surface_2))
            .setTitleColor(UiColors.resolve(this@AuditTrailActivity, R.color.ds_text_primary))
            .setTitleType(PersianDatePickerDialog.WEEKDAY_DAY_MONTH_YEAR)
            .setShowInBottomSheet(true)
            .setListener(object : ir.hamsaa.persiandatepicker.Listener {
                override fun onDateSelected(persianCalendar: PersianCalendar?) {
                    if (persianCalendar != null) {
                        val value = String.format(
                            Locale.US, "%04d/%02d/%02d",
                            persianCalendar.persianYear, persianCalendar.persianMonth, persianCalendar.persianDay
                        )
                        if (isFrom) fromDate = value else toDate = value
                        updateDateLabels()
                        loadLogs(reset = true)
                    }
                }

                override fun onDismissed() {}
            })
        picker.show()
    }

    private fun updateDateLabels() {
        btnFromDate.text = fromDate ?: getString(R.string.audit_trail_date_from)
        btnToDate.text = toDate ?: getString(R.string.audit_trail_date_to)
    }

    private fun selectedEntityType(): String? = entityTypeValues.getOrElse(spEntityType.selectedItemPosition) { null }

    private fun selectedAction(): String? = actionValues.getOrElse(spAction.selectedItemPosition) { null }

    private fun selectedEntityId(): Int? = etEntityId.text?.toString()?.trim()?.takeIf { it.isNotEmpty() }?.toIntOrNull()

    /** FIX (گروه۲/آیتم۸): عبارت جست‌وجوی نام (خالی ⇒ null تا فیلتر اعمال نشود). */
    private fun selectedSearch(): String? = etSearch.text?.toString()?.trim()?.takeIf { it.isNotEmpty() }

    /** همهٔ فیلترهای جاری در یک شیء — تا صفحه‌بندی و خروجی CSV دقیقاً یک چیز بفرستند. */
    private fun currentFilter() = AuditTrailFilter(
        entityType = selectedEntityType(),
        entityId = selectedEntityId(),
        action = selectedAction(),
        startDate = fromDate,
        endDate = toDate,
        search = selectedSearch()
    )

    // ------------------------------------------------------------------
    // بارگذاری (صفحه‌بندی)
    // ------------------------------------------------------------------
    private fun loadLogs(reset: Boolean) {
        if (isLoading) return
        isLoading = true
        val pageToLoad = if (reset) 1 else currentPage + 1

        if (reset) {
            tvEmpty.visibility = View.GONE
            progress.visibility = View.VISIBLE
        } else {
            btnLoadMore.isEnabled = false
            btnLoadMore.text = getString(R.string.audit_trail_loading_more)
        }

        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val response = repository.fetchPage(currentFilter(), pageToLoad, PAGE_SIZE)
                withContext(Dispatchers.Main) {
                    isLoading = false
                    progress.visibility = View.GONE
                    btnLoadMore.isEnabled = true
                    btnLoadMore.text = getString(R.string.audit_trail_load_more)

                    if (reset) logs.clear()
                    logs.addAll(response.logs)
                    currentPage = response.page
                    totalPages = response.pages
                    totalCount = response.total
                    render()
                }
            } catch (e: Exception) {
                if (e is kotlinx.coroutines.CancellationException) throw e
                withContext(Dispatchers.Main) {
                    isLoading = false
                    progress.visibility = View.GONE
                    btnLoadMore.isEnabled = true
                    btnLoadMore.text = getString(R.string.audit_trail_load_more)
                    val message = errorMessage(e)
                    if (logs.isEmpty()) {
                        tvEmpty.text = message
                        tvEmpty.visibility = View.VISIBLE
                    }
                    Toast.makeText(this@AuditTrailActivity, message, Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    private fun render() {
        if (logs.isEmpty()) {
            tvEmpty.text = getString(R.string.audit_trail_empty)
            tvEmpty.visibility = View.VISIBLE
            rvLogs.visibility = View.GONE
            tvSummary.text = getString(R.string.audit_trail_summary_empty)
        } else {
            tvEmpty.visibility = View.GONE
            rvLogs.visibility = View.VISIBLE
            adapter = AuditLogAdapter(logs).also { rvLogs.adapter = it }
            tvSummary.text = getString(R.string.audit_trail_summary, logs.size, totalCount, currentPage, maxOf(totalPages, 1))
        }
        val more = currentPage < totalPages
        btnLoadMore.visibility = if (more) View.VISIBLE else View.GONE
    }

    private fun errorMessage(e: Exception): String = AuditTrailLabels.errorMessage(this, e)

    // ------------------------------------------------------------------
    // خروجی CSV: همان فیلترها، بدون نیاز به تغییر سرور.
    // چون /audit-trail/logs فقط GET (JSON + صفحه‌بندی) است، CSV را سمت اپ از همان
    // مدل داده می‌سازیم (چند صفحه تا سقف MAX_EXPORT_PAGES) — نه فایل سرور.
    // ------------------------------------------------------------------
    private fun exportFilteredLogs() {
        if (isLoading) return
        isLoading = true
        progress.visibility = View.VISIBLE

        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val collected = repository.collectForExport(currentFilter(), EXPORT_PAGE_SIZE, MAX_EXPORT_PAGES)

                if (collected.isEmpty()) {
                    withContext(Dispatchers.Main) {
                        isLoading = false
                        progress.visibility = View.GONE
                        Toast.makeText(this@AuditTrailActivity,
                            getString(R.string.audit_trail_export_empty), Toast.LENGTH_LONG).show()
                    }
                    return@launch
                }

                val file = AuditTrailCsv.writeTo(this@AuditTrailActivity, collected)

                withContext(Dispatchers.Main) {
                    isLoading = false
                    progress.visibility = View.GONE
                    Toast.makeText(this@AuditTrailActivity,
                        getString(R.string.audit_trail_export_saved, file.absolutePath), Toast.LENGTH_LONG).show()
                    openExport(file)
                }
            } catch (e: Exception) {
                if (e is kotlinx.coroutines.CancellationException) throw e
                withContext(Dispatchers.Main) {
                    isLoading = false
                    progress.visibility = View.GONE
                    Toast.makeText(this@AuditTrailActivity,
                        getString(R.string.audit_trail_export_error, e.message ?: ""), Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    private fun openExport(file: File) {
        try {
            val uri: Uri = FileProvider.getUriForFile(this, "$packageName.provider", file)
            val viewIntent = Intent(Intent.ACTION_VIEW).apply {
                setDataAndType(uri, "text/csv")
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
            try {
                startActivity(viewIntent)
            } catch (_: ActivityNotFoundException) {
                val sendIntent = Intent(Intent.ACTION_SEND).apply {
                    type = "text/csv"
                    putExtra(Intent.EXTRA_STREAM, uri)
                    addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                }
                startActivity(Intent.createChooser(sendIntent, getString(R.string.audit_trail_export_share)))
            }
        } catch (_: Exception) {
            Toast.makeText(this, getString(R.string.audit_trail_export_open_failed, file.absolutePath), Toast.LENGTH_LONG).show()
        }
    }

    // ------------------------------------------------------------------
    // برچسب‌ها و دیف — منطقِ خالص به AuditTrailLabels.kt منتقل شد (فاز P4d، برش ۲).
    // این اعضا فقط واگذارکننده‌اند: امضایشان دقیقاً مثلِ قبل است تا هیچ call site ای
    // (از جمله Adapter داخلی و showDiffDialog) عوض نشود.
    // ------------------------------------------------------------------
    private fun displayActionLabel(item: AuditTrailLog): String = AuditTrailLabels.displayActionLabel(this, item)
    private fun entityRefsLine(item: AuditTrailLog): String = AuditTrailLabels.entityRefsLine(item)
    private fun displayDiff(item: AuditTrailLog): String = AuditTrailLabels.displayDiff(this, item)
    private fun displayActor(item: AuditTrailLog): String = AuditTrailLabels.displayActor(item)
    private fun parseColor(hex: String?): Int? = AuditTrailLabels.parseColor(hex)
    private fun actionIcon(action: String): String = AuditTrailLabels.actionIcon(action)
    private fun entityLabel(entityType: String): String = AuditTrailLabels.entityLabel(this, entityType)

    /** دیالوگ دیف کامل: فقط فیلدهای واقعاً تغییریافته، قبل/بعد + نام‌ها و کاربر تغییردهنده. */
    private fun showDiffDialog(item: AuditTrailLog) {
        val message = AuditTrailLabels.diffDialogMessage(this, item)

        val dialog = AlertDialog.Builder(this)
            .setTitle(getString(R.string.audit_trail_dialog_title, actionIcon(item.action)))
            .setMessage(message)
            .setPositiveButton(getString(R.string.audit_trail_dialog_ok), null)
            .setNeutralButton(getString(R.string.audit_trail_dialog_open_entity)) { _, _ ->
                openEntity(item)
            }
        // «لینک مستقیم به صورت‌حساب دانش‌آموز» فقط وقتی سرور دانش‌آموز را پیدا کرده باشد
        if (item.studentId != null) {
            dialog.setNegativeButton(getString(R.string.audit_trail_dialog_open_statement)) { _, _ ->
                openStudentStatement(item)
            }
        }
        dialog.show()
    }

    /** باز کردن صفحه‌ی مرتبط — فقط لینک‌های امن و در دسترس (بدون پارامترِ ناشناخته). */
    private fun openEntity(item: AuditTrailLog) {
        if (item.entityType == "installment") {
            startActivity(Intent(this, ReportActivity::class.java))
            toast(getString(R.string.audit_trail_open_installments_hint))
        } else {
            startActivity(Intent(this, TransactionManageActivity::class.java))
        }
    }

    /** FIX (گروه۲/آیتم۸): لینک مستقیم به صورت‌حساب دانش‌آموز — همان الگوی PersonListActivity
     *  (`StudentProfileActivity` با extra «STUDENT_ID» که صورت‌حساب/پرداخت‌ها را نشان می‌دهد). */
    private fun openStudentStatement(item: AuditTrailLog) {
        val studentId = item.studentId
        if (studentId == null) {
            toast(getString(R.string.audit_trail_no_student_link))
            return
        }
        val intent = Intent(this, StudentProfileActivity::class.java)
        intent.putExtra("STUDENT_ID", studentId)
        startActivity(intent)
    }

    private fun toast(message: String) = Toast.makeText(this, message, Toast.LENGTH_LONG).show()

    // ------------------------------------------------------------------
    // Adapter
    // ------------------------------------------------------------------
    inner class AuditLogAdapter(private val items: List<AuditTrailLog>) :
        RecyclerView.Adapter<AuditLogAdapter.VH>() {

        inner class VH(view: View) : RecyclerView.ViewHolder(view) {
            val card: MaterialCardView = view.findViewById(R.id.cardAuditLog)
            val tvIcon: TextView = view.findViewById(R.id.tvAuditLogIcon)
            val tvAction: TextView = view.findViewById(R.id.tvAuditLogAction)
            val tvEntity: TextView = view.findViewById(R.id.tvAuditLogEntity)
            val tvMeta: TextView = view.findViewById(R.id.tvAuditLogMeta)
            val tvRefs: TextView = view.findViewById(R.id.tvAuditLogRefs)
            val tvDiff: TextView = view.findViewById(R.id.tvAuditLogDiff)
            val tvIp: TextView = view.findViewById(R.id.tvAuditLogIp)
        }

        override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
            val view = LayoutInflater.from(parent.context)
                .inflate(R.layout.item_audit_trail_log, parent, false)
            return VH(view)
        }

        override fun getItemCount(): Int = items.size

        override fun onBindViewHolder(holder: VH, position: Int) {
            val item = items[position]
            holder.tvIcon.text = actionIcon(item.action)
            holder.tvAction.text = displayActionLabel(item)
            holder.tvEntity.text = getString(
                R.string.audit_trail_item_entity, entityLabel(item.entityType), item.entityId ?: 0
            )
            holder.tvMeta.text = getString(
                R.string.audit_trail_item_meta, displayActor(item).ifBlank { "—" }, item.timestamp
            )
            // FIX (گروه۲/آیتم۸): نام‌ها به‌جای شناسه‌ی خام (course_id/branch_id/student_id)
            val refs = entityRefsLine(item)
            if (refs.isBlank()) {
                holder.tvRefs.visibility = View.GONE
            } else {
                holder.tvRefs.visibility = View.VISIBLE
                holder.tvRefs.text = getString(R.string.audit_trail_refs_line, refs)
            }
            holder.tvDiff.text = displayDiff(item)
            holder.tvIp.text = getString(R.string.audit_trail_item_ip, item.ipAddress ?: "—")

            // رنگ آیکون/برچسب بر اساس «نوع تغییر» (سرور Material color می‌فرستد)
            val iconColor = parseColor(item.iconColor)
            if (iconColor != null) holder.tvIcon.setTextColor(iconColor)
            val actionColor = parseColor(item.actionColor)
            if (actionColor != null) holder.tvAction.setTextColor(actionColor)

            holder.card.setOnClickListener { showDiffDialog(item) }
            holder.tvEntity.setOnClickListener { openEntity(item) }
            // FIX (گروه۲/آیتم۸): تپ روی نام دانش‌آموز ⇒ مستقیم به صورت‌حساب او
            if (item.studentId != null) {
                holder.tvRefs.setOnClickListener { openStudentStatement(item) }
            } else {
                holder.tvRefs.setOnClickListener(null)
                holder.tvRefs.isClickable = false
            }
        }
    }

    companion object {
        private const val PAGE_SIZE = 50
        /** اندازهٔ صفحهٔ خروجی: همان ۲۰۰ ردیفِ قبلی، حالا نام‌دار. */
        private const val EXPORT_PAGE_SIZE = 200
        private const val MAX_EXPORT_PAGES = 10   // سقف ۲۰۰۰ ردیف در خروجی کلاینت‌ساید
    }
}
