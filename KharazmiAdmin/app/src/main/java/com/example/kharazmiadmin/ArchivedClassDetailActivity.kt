package com.example.kharazmiadmin

import android.content.Intent
import android.content.res.ColorStateList
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.CheckBox
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.TextView
import android.widget.Toast
import androidx.annotation.ColorRes
import androidx.appcompat.app.AlertDialog
import androidx.lifecycle.lifecycleScope
import com.google.android.material.button.MaterialButton
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import retrofit2.HttpException

/**
 * گزارش کامل یک کلاس حذف‌شده (صفحهٔ کامل با ظاهر پاپ‌آپ).
 *
 * تعداد دانش‌آموزان و فهرست‌شان، مجموع حاضر/غایب، غیبت موجه و غیرموجه، پرداخت‌شده و مانده‌ی هنگام حذف،
 * اطلاعات کلاس و تاریخچهٔ جلسات. فقط GET /admin/deleted_classes/{id} مصرف می‌شود؛ تنها عمل نوشتاری
 * صفحه «بازیابی» است که همان قرارداد قبلی (فقط متادیتا + تأیید صریح) را دارد.
 */
class ArchivedClassDetailActivity : BaseActivity() {

    companion object {
        const val EXTRA_COURSE_ID = "COURSE_ID"
    }

    private lateinit var api: DeletedClassesApi
    private lateinit var tvTitle: TextView
    private lateinit var tvTeacher: TextView
    private lateinit var tvCode: TextView
    private lateinit var tvDeleted: TextView
    private lateinit var progress: ProgressBar
    private lateinit var body: View
    private lateinit var rowOverview: LinearLayout
    private lateinit var rowAttendance1: LinearLayout
    private lateinit var rowAttendance2: LinearLayout
    private lateinit var rowFinance1: LinearLayout
    private lateinit var rowFinance2: LinearLayout
    private lateinit var pbRate: ProgressBar
    private lateinit var tvAttendanceNote: TextView
    private lateinit var tvFinanceNote: TextView
    private lateinit var tvInfo: TextView
    private lateinit var tvStudentsHeader: TextView
    private lateinit var llStudents: LinearLayout
    private lateinit var llSessions: LinearLayout
    private lateinit var btnShare: MaterialButton
    private lateinit var btnRestore: MaterialButton

    private var courseId: Int = -1
    private var detail: ArchivedClassDetail? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_archived_class_detail)

        courseId = intent.getIntExtra(EXTRA_COURSE_ID, -1)
        tvTitle = findViewById(R.id.tvDetailTitle)
        tvTeacher = findViewById(R.id.tvDetailTeacher)
        tvCode = findViewById(R.id.tvDetailCode)
        tvDeleted = findViewById(R.id.tvDetailDeleted)
        progress = findViewById(R.id.progressArchivedDetail)
        body = findViewById(R.id.llArchivedBody)
        rowOverview = findViewById(R.id.rowOverview)
        rowAttendance1 = findViewById(R.id.rowAttendance1)
        rowAttendance2 = findViewById(R.id.rowAttendance2)
        rowFinance1 = findViewById(R.id.rowFinance1)
        rowFinance2 = findViewById(R.id.rowFinance2)
        pbRate = findViewById(R.id.pbAttendanceRate)
        tvAttendanceNote = findViewById(R.id.tvAttendanceNote)
        tvFinanceNote = findViewById(R.id.tvFinanceNote)
        tvInfo = findViewById(R.id.tvDetailInfo)
        tvStudentsHeader = findViewById(R.id.tvStudentsHeader)
        llStudents = findViewById(R.id.llArchivedStudents)
        llSessions = findViewById(R.id.llArchivedSessions)
        btnShare = findViewById(R.id.btnArchivedShare)
        btnRestore = findViewById(R.id.btnArchivedRestore)

        api = RetrofitClient.getInstance(this).create(DeletedClassesApi::class.java)
        findViewById<MaterialButton>(R.id.btnArchivedDetailBack).setOnClickListener { finish() }
        btnShare.isEnabled = false
        btnRestore.isEnabled = false
        btnShare.setOnClickListener { shareReport() }
        btnRestore.setOnClickListener { confirmRestoreArchivedClass(courseId) }

        if (courseId <= 0) {
            Toast.makeText(this, getString(R.string.arch_detail_error), Toast.LENGTH_SHORT).show()
            finish()
            return
        }
        loadDetail()
    }

    private fun loadDetail() {
        progress.visibility = View.VISIBLE
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val d = api.getArchivedClassDetail(courseId)
                withContext(Dispatchers.Main) {
                    progress.visibility = View.GONE
                    detail = d
                    render(d)
                }
            } catch (e: Exception) {
                if (e is CancellationException) throw e
                withContext(Dispatchers.Main) {
                    progress.visibility = View.GONE
                    Toast.makeText(this@ArchivedClassDetailActivity, getString(R.string.arch_detail_error), Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    // ------------------------------------------------------------------
    // رندر — همهٔ فیلدها null-safe (رکورد legacy یا سرور قدیمی نباید «null» بنویسد یا کرش کند)
    // ------------------------------------------------------------------
    private fun render(d: ArchivedClassDetail) {
        val unknownPerson = getString(R.string.common_person_unknown)
        tvTitle.text = d.title?.takeIf { it.isNotBlank() } ?: getString(R.string.common_unknown_class)
        tvTeacher.text = getString(
            R.string.arch_d_teacher_branch,
            d.teacherName?.takeIf { it.isNotBlank() } ?: unknownPerson,
            d.branchName?.takeIf { it.isNotBlank() } ?: unknownPerson
        )
        val code = d.code?.trim().orEmpty()
        tvCode.visibility = if (code.isEmpty()) View.GONE else View.VISIBLE
        tvCode.text = getString(R.string.arch_row_code, code)
        tvDeleted.text = ArchiveFormat.deletedLine(this, d.deletedAtJalali, d.deletedWeekday, d.deletedAt)

        val students = d.students.orEmpty()
        val at = d.attendanceTotals ?: ArchivedAttendanceTotals()
        val fin = d.financeTotals ?: ArchivedFinanceTotals()

        // ---- نمای کلی ----
        rowOverview.removeAllViews()
        addTile(rowOverview, (d.students?.size ?: d.studentsCount).toString(), getString(R.string.arch_k_students), R.color.ds_accent)
        addTile(rowOverview, (d.sessionsHeld ?: d.sessionsCount).toString(), getString(R.string.arch_k_sessions), R.color.ds_info)
        addTile(
            rowOverview,
            at.attendanceRate?.let { "$it٪" } ?: getString(R.string.arch_rate_unknown),
            getString(R.string.arch_k_rate),
            rateColor(at.attendanceRate)
        )

        // ---- حضور و غیاب ----
        rowAttendance1.removeAllViews()
        rowAttendance2.removeAllViews()
        addTile(rowAttendance1, at.present.toString(), getString(R.string.arch_a_present), R.color.ds_success)
        addTile(rowAttendance1, at.absent.toString(), getString(R.string.arch_a_absent), R.color.ds_danger)
        addTile(rowAttendance2, at.absentUnexcused.toString(), getString(R.string.arch_a_unexcused), R.color.ds_danger)
        addTile(rowAttendance2, at.absentExcused.toString(), getString(R.string.arch_a_excused), R.color.ds_warning)
        pbRate.progress = at.attendanceRate ?: 0
        pbRate.progressTintList = ColorStateList.valueOf(UiColors.resolve(this, rateColor(at.attendanceRate)))
        val records = at.present + at.absent
        tvAttendanceNote.text = if (records == 0) getString(R.string.arch_a_note_none)
        else getString(R.string.arch_a_note, records, at.late)

        // ---- مالی ----
        rowFinance1.removeAllViews()
        rowFinance2.removeAllViews()
        addTile(rowFinance1, ArchiveFormat.money(fin.tuition), getString(R.string.arch_f_tuition), R.color.ds_text_primary)
        addTile(rowFinance1, ArchiveFormat.money(fin.paid), getString(R.string.arch_f_paid), R.color.ds_success)
        addTile(rowFinance2, ArchiveFormat.money(fin.debtTotal), getString(R.string.arch_f_debt), if (fin.debtTotal > 0) R.color.ds_danger else R.color.ds_success)
        addTile(rowFinance2, ArchiveFormat.money(fin.forgivenTotal), getString(R.string.arch_f_forgiven), R.color.ds_warning)
        tvFinanceNote.text = getString(if (d.hasSnapshot) R.string.arch_f_note_snapshot else R.string.arch_f_note_computed, fin.debtors)

        // ---- اطلاعات کلاس ----
        val info = mutableListOf<String>()
        d.gradeLevel?.takeIf { it.isNotBlank() }?.let { info += getString(R.string.arch_i_grade, it) }
        info += getString(
            R.string.arch_i_time,
            d.daysOfWeek?.takeIf { it.isNotBlank() } ?: "-",
            d.classTime?.takeIf { it.isNotBlank() } ?: "-"
        )
        if (!d.firstSessionDate.isNullOrBlank() || !d.lastSessionDate.isNullOrBlank()) {
            info += getString(R.string.arch_i_range, d.firstSessionDate?.takeIf { it.isNotBlank() } ?: "-", d.lastSessionDate?.takeIf { it.isNotBlank() } ?: "-")
        }
        roleLabel(d.requestedByRole)?.let { info += getString(R.string.arch_i_requested, it) }
        info += getString(R.string.arch_i_forgive, if (d.forgiveSessionCharges) getString(R.string.common_yes) else getString(R.string.common_no))
        d.adminNote?.takeIf { it.isNotBlank() }?.let { info += getString(R.string.arch_i_note, it) }
        info += getString(R.string.arch_i_counts, d.archivedEnrollmentsCount, d.archivedSessionsCount, d.transactionsCount)
        tvInfo.text = info.joinToString("\n")

        // ---- دانش‌آموزان: اول عدد (در عنوان)، زیرش فهرست ----
        tvStudentsHeader.text = getString(R.string.arch_s_students, students.size)
        llStudents.removeAllViews()
        if (students.isEmpty()) {
            llStudents.addView(plainText(getString(R.string.arch_st_empty)))
        } else {
            students.forEach { llStudents.addView(studentCard(it, llStudents)) }
        }

        // ---- تاریخچهٔ جلسات ----
        llSessions.removeAllViews()
        val sessions = d.sessionsHistory.orEmpty()
        if (sessions.isEmpty()) {
            llSessions.addView(plainText(getString(R.string.arch_se_empty)))
        } else {
            sessions.forEach { s ->
                llSessions.addView(
                    plainText(
                        getString(
                            R.string.arch_se_row,
                            s.weekday?.trim().orEmpty(), s.date?.trim().orEmpty(),
                            s.present, s.absent, s.absentUnexcused
                        ).trim()
                    )
                )
            }
        }

        // سرور قدیمی (قبل از نسخهٔ «گزارش کلاس حذفی») students/attendance_totals/finance_totals را
        // نمی‌فرستد؛ نمایش «۰ نفر / ۰ تومان» گمراه‌کننده است ⇒ به‌جای صفرِ قلابی، صریح می‌گوییم سرور قدیمی است.
        if (d.students == null && d.attendanceTotals == null && d.financeTotals == null) {
            val stale = getString(R.string.arch_stale_server)
            listOf(rowAttendance1, rowAttendance2, rowFinance1, rowFinance2).forEach { it.visibility = View.GONE }
            pbRate.visibility = View.GONE
            tvAttendanceNote.text = stale
            tvFinanceNote.text = stale
            tvStudentsHeader.text = getString(R.string.arch_s_students_plain)
            llStudents.removeAllViews()
            llStudents.addView(plainText(stale))
            llSessions.removeAllViews()
            llSessions.addView(plainText(stale))
        }

        body.visibility = View.VISIBLE
        btnShare.isEnabled = true
        btnRestore.isEnabled = true
    }

    private fun rateColor(rate: Int?): Int = when {
        rate == null -> R.color.ds_text_secondary
        rate >= 80 -> R.color.ds_success
        rate >= 50 -> R.color.ds_warning
        else -> R.color.ds_danger
    }

    private fun roleLabel(role: String?): String? = when (role?.trim()?.lowercase()) {
        "admin" -> getString(R.string.arch_role_admin)
        "secretary" -> getString(R.string.arch_role_secretary)
        "teacher" -> getString(R.string.arch_role_teacher)
        else -> null
    }

    private fun addTile(row: LinearLayout, value: String, label: String, @ColorRes tone: Int) {
        val tile = LayoutInflater.from(this).inflate(R.layout.item_archive_tile, row, false)
        val tv = tile.findViewById<TextView>(R.id.tvTileValue)
        tv.text = value
        tv.setTextColor(UiColors.resolve(this, tone))
        tile.findViewById<TextView>(R.id.tvTileLabel).text = label
        row.addView(tile)
    }

    private fun plainText(text: String): TextView = TextView(this).apply {
        this.text = text
        textSize = 13f
        setTextColor(UiColors.resolve(this@ArchivedClassDetailActivity, R.color.ds_text_primary))
        setPadding(0, 6, 0, 6)
        layoutParams = ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)
    }

    private fun studentCard(s: ArchivedStudentRow, parent: ViewGroup): View {
        val v = LayoutInflater.from(this).inflate(R.layout.item_archived_student, parent, false)
        v.findViewById<TextView>(R.id.tvStuName).text = s.name?.takeIf { it.isNotBlank() } ?: getString(R.string.common_person_unknown)
        val code = v.findViewById<TextView>(R.id.tvStuCode)
        if (s.studentCode != null) {
            code.visibility = View.VISIBLE
            code.text = getString(R.string.arch_st_code, s.studentCode)
        }
        val rate = v.findViewById<TextView>(R.id.tvStuRate)
        val r = s.attendanceRate
        if (r == null) {
            rate.text = getString(R.string.arch_st_rate_none)
            rate.setBackgroundResource(R.drawable.bg_ds_pill_neutral)
            rate.setTextColor(UiColors.resolve(this, R.color.ds_text_secondary))
        } else {
            rate.text = getString(R.string.arch_st_rate, r)
            when {
                r >= 80 -> { rate.setBackgroundResource(R.drawable.bg_ds_pill_success); rate.setTextColor(UiColors.resolve(this, R.color.ds_success_on_container)) }
                r >= 50 -> { rate.setBackgroundResource(R.drawable.bg_ds_pill_warning); rate.setTextColor(UiColors.resolve(this, R.color.ds_warning_on_container)) }
                else -> { rate.setBackgroundResource(R.drawable.bg_ds_pill_danger); rate.setTextColor(UiColors.resolve(this, R.color.ds_danger_on_container)) }
            }
        }
        v.findViewById<TextView>(R.id.tvStuAttendance).text = if (s.present + s.absent == 0)
            getString(R.string.arch_a_note_none)
        else getString(
            R.string.arch_st_att,
            s.present,
            if (s.late > 0) getString(R.string.arch_st_late, s.late) else "",
            s.absent, s.absentUnexcused, s.absentExcused
        )
        val money = StringBuilder(getString(R.string.arch_st_money, ArchiveFormat.money(s.paid), ArchiveFormat.money(s.debtTotal)))
        val sessionDebt = s.sessionDebtTeacher + s.sessionDebtInstitute
        if (sessionDebt > 0) money.append(getString(R.string.arch_st_money_sessions, ArchiveFormat.money(sessionDebt)))
        val forgiven = s.forgivenTeacher + s.forgivenInstitute
        if (forgiven > 0) money.append(getString(R.string.arch_st_forgiven, ArchiveFormat.money(forgiven)))
        val tvMoney = v.findViewById<TextView>(R.id.tvStuMoney)
        tvMoney.text = money.toString()
        tvMoney.setTextColor(UiColors.resolve(this, if (s.debtTotal > 0) R.color.ds_danger else R.color.ds_text_primary))
        return v
    }

    // ------------------------------------------------------------------
    // اشتراک‌گذاری متن گزارش (بدون فایل/مجوز: Intent.ACTION_SEND)
    // ------------------------------------------------------------------
    private fun shareReport() {
        val d = detail ?: return
        val at = d.attendanceTotals ?: ArchivedAttendanceTotals()
        val fin = d.financeTotals ?: ArchivedFinanceTotals()
        val sb = StringBuilder()
        sb.append(getString(R.string.arch_share_header, d.title?.takeIf { it.isNotBlank() } ?: getString(R.string.common_unknown_class), d.code.orEmpty())).append('\n')
        sb.append(tvTeacher.text).append('\n')
        sb.append(tvDeleted.text).append("\n\n")
        sb.append(getString(R.string.arch_s_students, d.students?.size ?: d.studentsCount)).append('\n')
        sb.append(getString(R.string.arch_a_present)).append(": ").append(at.present).append(" | ")
            .append(getString(R.string.arch_a_absent)).append(": ").append(at.absent).append(" | ")
            .append(getString(R.string.arch_a_unexcused)).append(": ").append(at.absentUnexcused).append(" | ")
            .append(getString(R.string.arch_a_excused)).append(": ").append(at.absentExcused).append("\n\n")
        sb.append(getString(R.string.arch_f_tuition)).append(": ").append(ArchiveFormat.money(fin.tuition)).append('\n')
        sb.append(getString(R.string.arch_f_paid)).append(": ").append(ArchiveFormat.money(fin.paid)).append('\n')
        sb.append(getString(R.string.arch_f_debt)).append(": ").append(ArchiveFormat.money(fin.debtTotal)).append("\n\n")
        d.students.orEmpty().forEach { s ->
            sb.append("• ").append(s.name?.takeIf { it.isNotBlank() } ?: getString(R.string.common_person_unknown))
                .append(" — ").append(getString(R.string.arch_a_present)).append(' ').append(s.present)
                .append(" / ").append(getString(R.string.arch_a_absent)).append(' ').append(s.absent)
                .append(" — ").append(getString(R.string.arch_f_debt)).append(": ").append(ArchiveFormat.money(s.debtTotal)).append('\n')
        }
        val send = Intent(Intent.ACTION_SEND).apply {
            type = "text/plain"
            putExtra(Intent.EXTRA_TEXT, sb.toString())
        }
        startActivity(Intent.createChooser(send, getString(R.string.arch_share_chooser)))
    }

    // ------------------------------------------------------------------
    // بازیابی کامل؛ سوابق مالی با چک‌باکس اختیاری و پیش‌فرض خاموش است.
    private fun confirmRestoreArchivedClass(courseId: Int) {
        val financialRestoreAvailable = detail?.financialRestoreAvailable == true
        val includeFinancialHistory = CheckBox(this).apply {
            text = getString(R.string.arch_restore_include_financial)
            isChecked = false
            isEnabled = financialRestoreAvailable
            val verticalPadding = (8 * resources.displayMetrics.density).toInt()
            setPadding(0, verticalPadding, 0, verticalPadding)
        }
        val padding = (24 * resources.displayMetrics.density).toInt()
        val content = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(padding, padding, padding, 0)
            addView(TextView(this@ArchivedClassDetailActivity).apply {
                text = getString(R.string.main_trash_restore_confirm_msg)
                setTextColor(UiColors.resolve(this@ArchivedClassDetailActivity, R.color.ds_text_primary))
            })
            addView(includeFinancialHistory)
            if (!financialRestoreAvailable) {
                addView(TextView(this@ArchivedClassDetailActivity).apply {
                    text = getString(R.string.arch_restore_financial_unavailable)
                    textSize = 13f
                    setTextColor(UiColors.resolve(this@ArchivedClassDetailActivity, R.color.ds_text_secondary))
                })
            }
        }

        AlertDialog.Builder(this)
            .setTitle(getString(R.string.main_trash_restore_confirm_title))
            .setView(content)
            .setPositiveButton(getString(R.string.main_trash_restore)) { _, _ ->
                restoreArchivedClass(courseId, includeFinancialHistory.isChecked)
            }
            .setNegativeButton(getString(R.string.btn_cancel), null)
            .show()
    }

    private fun restoreArchivedClass(courseId: Int, includeFinancialHistory: Boolean) {
        btnRestore.isEnabled = false
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val result = api.restoreArchivedClass(
                    courseId,
                    ClassRestoreRequest(includeFinancialHistory = includeFinancialHistory)
                )
                withContext(Dispatchers.Main) {
                    // هشدارهای سرور (معلم آرشیوشده یا provenance قدیمی) در دیالوگ دیده شوند.
                    val warnings = result.warnings.orEmpty().filter { it.isNotBlank() }
                    if (warnings.isNotEmpty()) {
                        AlertDialog.Builder(this@ArchivedClassDetailActivity)
                            .setTitle(R.string.main_trash_restore_warnings_title)
                            .setMessage(warnings.joinToString("\n\n") { "• $it" })
                            .setPositiveButton(R.string.common_ok, null)
                            .setOnDismissListener { finish() }
                            .show()
                    } else {
                        val msg = result.message?.takeIf { it.isNotBlank() }
                            ?: getString(R.string.main_trash_restore_ok)
                        Toast.makeText(this@ArchivedClassDetailActivity, msg, Toast.LENGTH_LONG).show()
                        finish()
                    }
                }
            } catch (e: Exception) {
                if (e is CancellationException) throw e
                withContext(Dispatchers.Main) {
                    btnRestore.isEnabled = true
                    Toast.makeText(
                        this@ArchivedClassDetailActivity,
                        restoreErrorMessage(e),
                        Toast.LENGTH_LONG
                    ).show()
                }
            }
        }
    }

    private fun restoreErrorMessage(error: Throwable): String {
        val body = (error as? HttpException)?.response()?.errorBody()?.string()
        val detail = runCatching { JSONObject(body.orEmpty()).optString("detail") }.getOrNull()
        return detail?.takeIf { it.isNotBlank() }
            ?: getString(R.string.main_trash_restore_fail)
    }

}
