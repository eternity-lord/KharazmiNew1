package com.example.kharazmiadmin

// مدل‌های DTO فیش/رسید — از InvoiceActivity.kt بیرون کشیده شدند (P4d slice 4).
//
// چرا اینجا و نه کنارِ APIها؟ چون این چهار مدل بین چند مصرف‌کننده مشترک‌اند:
//   • InvoiceActivity        (lastReceipt: ReceiptDetailsResponse و …)
//   • RemittancePrintApi     (PrintReceiptRequest/Response, PdfReceiptResponse)
//   • ReceiptDetailsApi      (ReceiptDetailsResponse)
// پس در فایلِ مدل‌ها می‌مانند (هم‌راستا با سابقِ AppModels.kt) تا حذفِ احتمالیِ
// RemittancePrintApi در آینده، جایِ این‌ها را تکان ندهد.
//
// توجه: هیچ رفتاری تغییر نکرده — بدنه‌ها و مقدارهای پیش‌فرض عیناً منتقل شده‌اند.
// `tests/route_audit/kotlin_contract.py::discover_models()` با rglob روی کلِ
// ANDROID_SRC اسکن می‌کند و کلیدش فقط نامِ کلاس است، پس کشفِ قرارداد دست‌نخورده می‌ماند.

// Print Receipt Request Model
data class PrintReceiptRequest(val transaction_id: Int)

// Print Receipt Response Model
data class PrintReceiptResponse(
    val status: String,
    val message: String,
    val print_job_id: String? = null,
    val receipt_data: Map<String, Any>? = null
)

// PDF Receipt Response Model
data class PdfReceiptResponse(
    val status: String,
    val message: String,
    val pdf_filename: String? = null,
    val receipt_data: Map<String, Any>? = null
)


// FIX H16: جزئیات رسیدِ سرور-محور برای چاپ مجدد (به‌جای اعتماد به Intent extras).
data class ReceiptDetailsResponse(
    val transaction_id: Int,
    val remittance_number: Any? = null,
    val student_name: String? = null,
    val student_national_code: String? = null,
    val amount: Long? = null,
    val payment_method: String? = null,
    val tracking_code: String? = null,
    val date: String? = null,
    val description: String? = null,
    val target_wallet: String? = null,
    val type: String? = null,
    val is_reversed: Boolean? = null,
    val course_name: String? = null,
    // چاپ حواله: کدام معلم، برای چند جلسه، به کدام کیف پول واریز شده (سرور قدیمی نمی‌فرستد → null)
    val course_code: String? = null,
    val teacher_name: String? = null,
    val sessions_covered: Int? = null,
    val wallet_label: String? = null,
    val paid_to_name: String? = null,
    val class_remaining_teacher: Long? = null,
    val class_remaining_institute: Long? = null
)
