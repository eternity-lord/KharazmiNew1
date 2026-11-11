package com.example.kharazmiadmin

import android.content.Context
import java.util.Locale

/**
 * برچسب‌ها، قالب‌بندی و خلاصهٔ دیفِ ممیزی مالی — لایهٔ نمایشِ خالص.
 *
 * از `AuditTrailActivity` بیرون کشیده شد (فاز P4d، برش ۲). این توابع «فقط نمایش» هستند:
 * هیچ عدد مالی را تغییر نمی‌دهند، وضعیتِ شبکه ندارند و به View یا Activity وابسته نیستند،
 * پس با یک `Context` ساده قابل آزمایش‌اند. قراردادِ `context` به‌عنوانِ پارامترِ اول
 * دقیقاً همان الگویِ `EnrollmentLabels` و `ReportHints` در همین بسته است.
 *
 * بدنه‌ها کلمه‌به‌کلمه از Activity منتقل شده‌اند؛ تنها تفاوت، صریح شدنِ `Context` برای
 * `getString` است تا رفتارِ منابع (locale و night mode) دقیقاً مثلِ قبل بماند.
 */
object AuditTrailLabels {

    /** متنِ دیالوگِ دیف کامل: فقط فیلدهای واقعاً تغییریافته، قبل/بعد + نام‌ها و کاربر تغییردهنده.
     *
     * از AuditTrailActivity.showDiffDialog بیرون کشیده شد (فاز P4d برش ۲): ساختِ متن خالص است،
     * ولی خودِ AlertDialog و ناوبری در Activity ماندند چون به lifecycle و Intent نیاز دارند. */
    fun diffDialogMessage(context: Context, item: AuditTrailLog): String {
        val changed = item.changedFields.filter { it != "id" }.ifEmpty { item.changedFields }
        val builder = StringBuilder()
        builder.append(context.getString(R.string.audit_trail_dialog_meta,
            displayActionLabel(context, item), entityLabel(context, item.entityType), item.entityId ?: 0))
        // FIX (گروه۲/آیتم۸): «کاربر تغییردهنده» — اگر لاگ ممیزی کاربر نداشت، سرور از
        // ActivityLog همان عملیات نام را برگردانده (actor_source = activity_log).
        val actor = displayActor(item)
        builder.append("\n").append(
            when {
                actor.isBlank() -> context.getString(R.string.audit_trail_dialog_actor_unknown)
                item.actorSource == "activity_log" && !item.actorAction.isNullOrBlank() ->
                    context.getString(R.string.audit_trail_dialog_actor_activity, actor, item.actorAction)
                else -> context.getString(R.string.audit_trail_dialog_actor, actor)
            }
        )
        builder.append("\n").append(context.getString(R.string.audit_trail_dialog_user, item.username ?: "—", item.timestamp))
        builder.append("\n").append(context.getString(R.string.audit_trail_dialog_ip, item.ipAddress ?: "—"))
        val refs = entityRefsLine(item)
        if (refs.isNotBlank()) {
            builder.append("\n").append(context.getString(R.string.audit_trail_dialog_refs, refs))
        }
        builder.append("\n\n")
        if (changed.isEmpty()) {
            builder.append(context.getString(R.string.audit_trail_no_field_detail))
        } else {
            for (field in changed) {
                val before = formatReferenceValue(item, field, item.oldValues?.get(field))
                val after = formatReferenceValue(item, field, item.newValues?.get(field))
                // برچسب فارسی ستون از سرور (labels) و در نبودش mapping محلی
                val label = item.labels?.get(field)?.takeIf { it.isNotBlank() } ?: friendlyFieldName(context, field)
                builder.append("• $label: $before → $after\n")
            }
        }

        return builder.toString()
    }

    fun errorMessage(context: Context, e: Exception): String = when {
        e is retrofit2.HttpException && e.code() == 403 -> context.getString(R.string.audit_trail_forbidden)
        e is retrofit2.HttpException && e.code() == 401 -> context.getString(R.string.audit_trail_session_expired)
        e is retrofit2.HttpException -> context.getString(R.string.audit_trail_server_error, e.code())
        else -> e.message ?: context.getString(R.string.audit_trail_unknown_error)
    }

    // ------------------------------------------------------------------
    // برچسب‌ها و دیف
    // ------------------------------------------------------------------
    fun actionLabel(context: Context, action: String): String = when (action) {
        "create" -> context.getString(R.string.audit_trail_action_create)
        "update" -> context.getString(R.string.audit_trail_action_update)
        "delete" -> context.getString(R.string.audit_trail_action_delete)
        else -> action
    }

    // ------------------------------------------------------------------
    // FIX (گروه۲/آیتم۸): مصرف فیلدهای غنی‌شده‌ی سرور — نام‌ها به‌جای شناسه‌ی خام،
    // نوع تغییر به زبان ساده، کاربر تغییردهنده (با fallback روی ActivityLog)،
    // لینک صورت‌حساب دانش‌آموز و رنگ هر نوع تغییر. همه با fallback به رفتار قبلی
    // (اگر سرور قدیمی باشد، فیلدها null می‌آیند و همان نمایش قبلی دیده می‌شود).
    // ------------------------------------------------------------------
    /** برچسب فارسی عملیات: اولویت با سرور؛ سرور قدیمی ⇒ همان mapping محلی. */
    fun displayActionLabel(context: Context, item: AuditTrailLog): String =
        item.actionLabel?.takeIf { it.isNotBlank() } ?: actionLabel(context, item.action)

    /** «مربوط به: سینا مرادی • ریاضی کنکور • شعبه مرکزی» — خالی اگر سرور نامی نفرستاد. */
    fun entityRefsLine(item: AuditTrailLog): String {
        val refs = item.entityRefs ?: return ""
        val parts = listOfNotNull(
            refs["student"]?.takeIf { it.isNotBlank() },
            refs["teacher"]?.takeIf { it.isNotBlank() },
            refs["course"]?.takeIf { it.isNotBlank() },
            refs["enrollment"]?.takeIf { it.isNotBlank() && refs["student"].isNullOrBlank() },
            refs["branch"]?.takeIf { it.isNotBlank() }
        ).distinct()
        return parts.joinToString(" • ")
    }

    /** خلاصه‌ی تغییر: جمله‌ی آماده‌ی سرور (با برچسب فارسی و هزارگان) یا ساخت محلی. */
    fun displayDiff(context: Context, item: AuditTrailLog): String =
        item.changeSummary?.takeIf { it.isNotBlank() } ?: diffSummaryFor(context, item)

    /** نام کاربر تغییردهنده: `username` لاگ ممیزی، وگرنه fallback سرور از ActivityLog. */
    fun displayActor(item: AuditTrailLog): String =
        item.username?.takeIf { it.isNotBlank() }
            ?: item.actorUsername?.takeIf { it.isNotBlank() }
            ?: ""

    /** رنگ هر نوع تغییر (سرور Material color می‌فرستد) ⇒ null اگر قابل پارس نبود. */
    fun parseColor(hex: String?): Int? = try {
        hex?.takeIf { it.startsWith("#") && it.length == 7 }?.let { android.graphics.Color.parseColor(it) }
    } catch (_: Exception) {
        null
    }

    fun actionIcon(action: String): String = when (action) {
        "create" -> "➕"
        "update" -> "✏️"
        "delete" -> "🗑️"
        else -> "•"
    }

    fun entityLabel(context: Context, entityType: String): String = when (entityType) {
        "transaction" -> context.getString(R.string.audit_trail_entity_transaction)
        "installment" -> context.getString(R.string.audit_trail_entity_installment)
        else -> entityType
    }

    fun friendlyFieldName(context: Context, field: String): String = when (field) {
        "amount" -> context.getString(R.string.audit_trail_field_amount)
        "is_paid" -> context.getString(R.string.audit_trail_field_is_paid)
        "paid_amount" -> context.getString(R.string.audit_trail_field_paid_amount)
        "paid_at" -> context.getString(R.string.audit_trail_field_paid_at)
        "due_date" -> context.getString(R.string.audit_trail_field_due_date)
        "is_deleted" -> context.getString(R.string.audit_trail_field_is_deleted)
        "is_reversed" -> context.getString(R.string.audit_trail_field_is_reversed)
        "payment_method" -> context.getString(R.string.audit_trail_field_payment_method)
        "description" -> context.getString(R.string.audit_trail_field_description)
        "date" -> context.getString(R.string.audit_trail_field_date)
        "target_wallet" -> context.getString(R.string.audit_trail_field_target_wallet)
        "student_id" -> context.getString(R.string.audit_trail_field_student)
        "enrollment_id" -> context.getString(R.string.audit_trail_field_enrollment)
        "course_id" -> context.getString(R.string.audit_trail_field_course)
        "branch_id" -> context.getString(R.string.audit_trail_field_branch)
        "teacher_id" -> context.getString(R.string.audit_trail_field_teacher)
        "session_id" -> context.getString(R.string.audit_trail_field_session)
        else -> field
    }

    fun formatReferenceValue(item: AuditTrailLog, field: String, value: Any?): String {
        if (field == "course_id") return item.entityRefs?.get("course")?.takeIf { it.isNotBlank() } ?: formatValue(value)
        if (field == "branch_id") return item.entityRefs?.get("branch")?.takeIf { it.isNotBlank() } ?: formatValue(value)
        if (field == "student_id") return item.entityRefs?.get("student")?.takeIf { it.isNotBlank() } ?: formatValue(value)
        if (field == "teacher_id") return item.entityRefs?.get("teacher")?.takeIf { it.isNotBlank() } ?: formatValue(value)
        if (field == "enrollment_id") return item.entityRefs?.get("enrollment")?.takeIf { it.isNotBlank() } ?: formatValue(value)
        return formatValue(value)
    }

    fun formatValue(value: Any?): String {
        if (value == null) return "—"
        val text = when (value) {
            is Double -> if (value == value.toLong().toDouble()) value.toLong().toString() else value.toString()
            is Map<*, *>, is List<*> -> value.toString()
            else -> value.toString()
        }
        if (text.length > 60) return text.take(60) + "…"
        // اعداد بزرگ را با جداکننده‌ی هزارگان نشان بده (مبلغ‌ها خواناتر شوند)
        val long = text.toLongOrNull()
        return if (long != null && kotlin.math.abs(long) >= 1000) String.format(Locale.US, "%,d", long) else text
    }

    fun diffSummaryFor(context: Context, item: AuditTrailLog): String {
        val changed = item.changedFields.filter { it != "id" }
        if (changed.isEmpty()) return context.getString(R.string.audit_trail_no_field_detail)
        return changed.take(3).joinToString(" • ") { field ->
            val before = item.oldValues?.get(field)
            val after = item.newValues?.get(field)
            when (item.action) {
                "create" -> "${friendlyFieldName(context, field)}: ${formatReferenceValue(item, field, after)}"
                "delete" -> "${friendlyFieldName(context, field)}: ${formatReferenceValue(item, field, before)}"
                else -> "${friendlyFieldName(context, field)}: ${formatReferenceValue(item, field, before)} → ${formatReferenceValue(item, field, after)}"
            }
        } + if (changed.size > 3) " …" else ""
    }
}
