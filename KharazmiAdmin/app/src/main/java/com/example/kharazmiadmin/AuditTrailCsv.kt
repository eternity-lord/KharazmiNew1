package com.example.kharazmiadmin

import android.content.Context
import java.io.File
import java.io.FileOutputStream

/**
 * خروجی CSV ممیزی مالی — از `AuditTrailActivity` بیرون کشیده شد (فاز P4d، برش ۲).
 *
 * سرور برای `/audit-trail/logs` فقط JSONِ صفحه‌بندی‌شده می‌دهد، پس CSV سمتِ اپ از همان
 * مدلِ داده ساخته می‌شود (بدونِ endpoint جدید و بدونِ تغییر در سرور). مهارِ
 * فرمول‌اینجکشن (`= + - @`) و BOM دقیقاً مثلِ قبل است تا خروجیِ اکسل امن بماند.
 */
object AuditTrailCsv {

    /** BOM تا اکسلِ ویندوز UTF-8 را درست بفهمد. */
    val CSV_BOM = byteArrayOf(0xEF.toByte(), 0xBB.toByte(), 0xBF.toByte())

    fun exportFileName(): String = "audit_trail_${System.currentTimeMillis()}.csv"

    fun csvText(context: Context, items: List<AuditTrailLog>): String {
        val header = context.getString(R.string.audit_trail_csv_header)
        val builder = StringBuilder(header).append("\r\n")
        for (item in items) {
            val row = listOf(
                item.timestamp,
                item.username ?: "",
                AuditTrailLabels.displayActionLabel(context, item),
                AuditTrailLabels.entityLabel(context, item.entityType),
                item.entityId?.toString() ?: "",
                item.changedLabels?.joinToString("; ")?.takeIf { it.isNotBlank() }
                    ?: item.changedFields.joinToString("; "),
                AuditTrailLabels.displayDiff(context, item),
                item.ipAddress ?: "",
                // FIX (گروه۲/آیتم۸): ستون‌های جدید — کاربر تغییردهنده (با fallback) و نام‌ها
                AuditTrailLabels.displayActor(item),
                AuditTrailLabels.entityRefsLine(item)
            )
            builder.append(row.joinToString(",") { csvCell(it) }).append("\r\n")
        }
        return builder.toString()
    }

    /** استاندارد CSV: quote + escape؛ و مهار فرمول‌اینجکشن (= + - @) مثل خروجی‌های سرور. */
    fun csvCell(raw: String): String {
        var value = raw
        val first = value.firstOrNull()
        if (first == '=' || first == '+' || first == '-' || first == '@') value = "'$value"
        return "\"" + value.replace("\"", "\"\"") + "\""
    }

    /** نوشتنِ BOM + متنِ CSV در حافظهٔ خارجیِ اپ و برگرداندنِ فایلِ ساخته‌شده. */
    fun writeTo(context: Context, items: List<AuditTrailLog>): File {
        val file = File(context.getExternalFilesDir(null), exportFileName())
        FileOutputStream(file).use { output ->
            output.write(CSV_BOM)
            output.write(csvText(context, items).toByteArray(Charsets.UTF_8))
        }
        return file
    }
}
