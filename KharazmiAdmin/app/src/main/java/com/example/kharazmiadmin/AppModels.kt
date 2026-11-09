package com.example.kharazmiadmin

import com.google.gson.annotations.SerializedName

// ==========================================
// 1. عمومی و پاسخ‌های ساده
// ==========================================
data class SimpleResponse(val message: String, val price_warning: String? = null) // FIX (audit-v2/blind-approve-2c): هشدار مبلغ؛ غایب=Gson→null و همه مصرف‌کننده‌های قبلی سالم

// پاسخ اختصاصی برای تعلیق
data class SuspendResponse(val message: String, val is_suspended: Boolean)

// ==========================================
// 2. احراز هویت (Auth)
// ==========================================
data class LoginRequest(val mobile: String, val password: String?)
data class LoginResponse(
    val status: String,
    val role: String,
    val user_id: Int,
    val name: String,
    val message: String,
    val sub_role: String? = null,
    val token: String? = null,
    val branch_id: Int? = null
)

data class DeviceTokenRequest(
    @SerializedName("token") val token: String
)

data class ChangePasswordRequest(
    val mobile: String,
    val old_password: String,
    val new_password: String
)

// ==========================================
// 3. معلمان (Teachers)
// ==========================================
data class TeacherRegisterData(
    val first_name: String,
    val last_name: String,
    val father_name: String,
    val national_code: String,
    val birth_date: String,
    val mobile: String,
    val password: String,
    val home_phone: String,
    val card_number: String,
    val marital_status: String,
    val gender: String,
    val employment_type: String,
    val profile_image: String? = null
)

// FIX(null-data): نام legacy ممکن است null/خالی باشد — null‌پذیر تا یک رکورد ناقص
// لیست مربیان (انتخاب معلم در کلاس) را نشکند؛ فال‌بک در محل نمایش.
data class TeacherSimple(
    val id: Int,
    val first_name: String? = null,
    val last_name: String? = null
)

// ==========================================
// 4. دانش‌آموزان (Students)
// ==========================================
data class StudentRegisterData(
    val first_name: String,
    val last_name: String,
    val father_name: String,
    val national_code: String,
    val birth_date: String,
    val student_mobile: String,
    val parent_mobile: String,
    val home_phone: String,
    val address: String,
    val study_status: String,
    val gender: String
)

data class RegisterResponse(val message: String, val id: Int, val teacher_code: Int? = null, val initial_password: String? = null)

data class StudentSearchItem(val id: Int, val name: String)
data class SearchItem(val id: Int, val name: String)

data class StudentItem(
    val student_id: Int,
    val student_name: String,
    val debt: Long,
    val enrollment_id: Int,
    val debt_teacher: Long = 0,
    val debt_institute: Long = 0,
    val course_id: Int? = null,
    val course_title: String? = null,
    val teacher_id: Int? = null,
    val teacher_name: String? = null,
    val is_unassigned: Boolean = false
)

// ==========================================
// 5. کلاس‌ها (Classes)
// ==========================================
data class ClassSubmitData(
    val title: String,
    val code: String,
    val teacher_id: Int,
    val education_type: String,
    val grade_level: String,
    val gender_type: String,
    val days_of_week: String,
    val class_time: String,
    val teacher_session_price: Long,
    val bg_color: String,
    val is_admin_created: Boolean = false
)

data class ClassResponse(val message: String, val id: Int, val status: String? = "success")

data class ClassItem(val id: Int, val title: String, val code: String)

data class ClassItemFull(
    val id: Int, val title: String, val code: String,
    val days_of_week: String, val class_time: String
)

data class PendingClassItem(
    val id: Int,
    val title: String? = null,
    val teacher_name: String? = null,
    val teacher_price: Long? = null,
    val days: String? = null,
    val time: String? = null,
    val base_institute_share: Long? = null,
    val code: String? = null,
    val teacher_id: Int? = null,
    val capacity: Int? = null,
    val branch_id: Int? = null,
    val rejection_reason: String? = null,
    val pending_since: String? = null,
    // Gson can legally materialize a JSON null even when the Kotlin default is a list;
    // keep the wire model nullable and normalize at the adapter boundary.
    val conflict_course_ids: List<Int>? = null,
    val has_schedule_conflict: Boolean = false
)

data class ClassDetailsResponse(val students: List<StudentItem>)

// FIX(archive): آرشیو کلاس‌های حذف‌شده پاسخ متفاوتی از «کلاس‌های در انتظار» دارد
// (teacher_price/days/time/base_institute_share در آرشیو نیست و title/code می‌توانند null باشند؛
// مدل قبلی PendingClassItem همین‌ها را non-null می‌خواست ⇒ نمایش اشتباه/خالی).
data class ArchivedClassItem(
    val id: Int,
    @SerializedName("title") val title: String? = null,
    @SerializedName("code") val code: String? = null,
    @SerializedName("teacher_id") val teacherId: Int? = null,
    @SerializedName("teacher_name") val teacherName: String? = null,
    @SerializedName("branch_id") val branchId: Int? = null,
    @SerializedName("branch_name") val branchName: String? = null,
    @SerializedName("grade_level") val gradeLevel: String? = null,
    @SerializedName("days_of_week") val daysOfWeek: String? = null,
    @SerializedName("class_time") val classTime: String? = null,
    @SerializedName("students_count") val studentsCount: Int = 0,
    @SerializedName("students_active_count") val studentsActiveCount: Int = 0,
    @SerializedName("sessions_count") val sessionsCount: Int = 0,
    @SerializedName("transactions_count") val transactionsCount: Int = 0,
    @SerializedName("deleted_at") val deletedAt: String? = null,
    // تاریخ حذف جلالی + روز هفته (سرور قدیمی نمی‌فرستد ⇒ null و به deletedAt برمی‌گردیم)
    @SerializedName("deleted_at_jalali") val deletedAtJalali: String? = null,
    @SerializedName("deleted_weekday") val deletedWeekday: String? = null,
    @SerializedName("forgive_session_charges") val forgiveSessionCharges: Boolean = false,
    @SerializedName("is_suspended") val isSuspended: Boolean = false,
    @SerializedName("bg_color") val bgColor: String? = null
)

data class ArchivedClassDetail(
    val id: Int,
    @SerializedName("title") val title: String? = null,
    @SerializedName("code") val code: String? = null,
    @SerializedName("grade_level") val gradeLevel: String? = null,
    @SerializedName("days_of_week") val daysOfWeek: String? = null,
    @SerializedName("class_time") val classTime: String? = null,
    @SerializedName("is_suspended") val isSuspended: Boolean = false,
    @SerializedName("teacher_id") val teacherId: Int? = null,
    @SerializedName("teacher_name") val teacherName: String? = null,
    @SerializedName("branch_id") val branchId: Int? = null,
    @SerializedName("branch_name") val branchName: String? = null,
    @SerializedName("students_count") val studentsCount: Int = 0,
    @SerializedName("students_active_count") val studentsActiveCount: Int = 0,
    @SerializedName("archived_enrollments_count") val archivedEnrollmentsCount: Int = 0,
    @SerializedName("sessions_count") val sessionsCount: Int = 0,
    @SerializedName("archived_sessions_count") val archivedSessionsCount: Int = 0,
    @SerializedName("transactions_count") val transactionsCount: Int = 0,
    @SerializedName("transactions_total") val transactionsTotal: Long = 0,
    @SerializedName("deleted_at") val deletedAt: String? = null,
    @SerializedName("has_deletion_record") val hasDeletionRecord: Boolean = false,
    @SerializedName("financial_restore_available") val financialRestoreAvailable: Boolean = false,
    @SerializedName("forgive_session_charges") val forgiveSessionCharges: Boolean = false,
    @SerializedName("requested_by_role") val requestedByRole: String? = null,
    @SerializedName("admin_note") val adminNote: String? = null,
    // ---- گزارش کامل تاریخی (همه nullable/پیش‌فرض‌دار: سرور قدیمی فقط فیلدهای بالا را می‌فرستد) ----
    @SerializedName("deleted_at_jalali") val deletedAtJalali: String? = null,
    @SerializedName("deleted_weekday") val deletedWeekday: String? = null,
    @SerializedName("students") val students: List<ArchivedStudentRow>? = null,
    @SerializedName("attendance_totals") val attendanceTotals: ArchivedAttendanceTotals? = null,
    @SerializedName("finance_totals") val financeTotals: ArchivedFinanceTotals? = null,
    @SerializedName("sessions_held") val sessionsHeld: Int? = null,
    @SerializedName("sessions_history") val sessionsHistory: List<ArchivedSessionRow>? = null,
    @SerializedName("first_session_date") val firstSessionDate: String? = null,
    @SerializedName("last_session_date") val lastSessionDate: String? = null,
    @SerializedName("has_snapshot") val hasSnapshot: Boolean = false
)

data class ArchivedStudentRow(
    @SerializedName("student_id") val studentId: Int = 0,
    @SerializedName("name") val name: String? = null,
    @SerializedName("student_code") val studentCode: Int? = null,
    @SerializedName("present") val present: Int = 0,
    @SerializedName("late") val late: Int = 0,
    @SerializedName("absent") val absent: Int = 0,
    @SerializedName("absent_excused") val absentExcused: Int = 0,
    @SerializedName("absent_unexcused") val absentUnexcused: Int = 0,
    @SerializedName("attendance_rate") val attendanceRate: Int? = null,
    @SerializedName("tuition") val tuition: Long = 0,
    @SerializedName("paid") val paid: Long = 0,
    @SerializedName("tuition_debt") val tuitionDebt: Long = 0,
    @SerializedName("session_debt_teacher") val sessionDebtTeacher: Long = 0,
    @SerializedName("session_debt_institute") val sessionDebtInstitute: Long = 0,
    @SerializedName("debt_total") val debtTotal: Long = 0,
    @SerializedName("forgiven_teacher") val forgivenTeacher: Long = 0,
    @SerializedName("forgiven_institute") val forgivenInstitute: Long = 0,
    @SerializedName("finance_source") val financeSource: String? = null
)

data class ArchivedAttendanceTotals(
    @SerializedName("present") val present: Int = 0,
    @SerializedName("late") val late: Int = 0,
    @SerializedName("absent") val absent: Int = 0,
    @SerializedName("absent_excused") val absentExcused: Int = 0,
    @SerializedName("absent_unexcused") val absentUnexcused: Int = 0,
    @SerializedName("attendance_rate") val attendanceRate: Int? = null
)

data class ArchivedFinanceTotals(
    @SerializedName("tuition") val tuition: Long = 0,
    @SerializedName("paid") val paid: Long = 0,
    @SerializedName("tuition_debt") val tuitionDebt: Long = 0,
    @SerializedName("session_debt") val sessionDebt: Long = 0,
    @SerializedName("debt_total") val debtTotal: Long = 0,
    @SerializedName("debtors") val debtors: Int = 0,
    @SerializedName("forgiven_total") val forgivenTotal: Long = 0
)

data class ArchivedSessionRow(
    @SerializedName("session_id") val sessionId: Int = 0,
    @SerializedName("date") val date: String? = null,
    @SerializedName("weekday") val weekday: String? = null,
    @SerializedName("present") val present: Int = 0,
    @SerializedName("absent") val absent: Int = 0,
    @SerializedName("absent_excused") val absentExcused: Int = 0,
    @SerializedName("absent_unexcused") val absentUnexcused: Int = 0
)

// بازیابی کامل کلاس و تاریخچهٔ عملیاتی؛ برگرداندن سوابق مالی انتخابی و پیش‌فرض خاموش است.
data class ClassRestoreRequest(
    @SerializedName("mode") val mode: String = "full",
    @SerializedName("include_financial_history") val includeFinancialHistory: Boolean = false,
    @SerializedName("reason") val reason: String? = null
)

data class ClassRestoreResponse(
    @SerializedName("message") val message: String? = null,
    @SerializedName("id") val id: Int? = null,
    @SerializedName("title") val title: String? = null,
    @SerializedName("mode") val mode: String? = null,
    @SerializedName("include_financial_history") val includeFinancialHistory: Boolean = false,
    @SerializedName("financial_restore_available") val financialRestoreAvailable: Boolean = false,
    @SerializedName("finances_untouched") val financesUntouched: Boolean = false,
    @SerializedName("note") val note: String? = null,
    // O-13: هشدارهای سرور دربارهٔ بازیابی (مثلاً «معلم این کلاس آرشیو شده است») — nullable و
    // با default تا با سرور قدیمی هم سازگار باشد.
    @SerializedName("warnings") val warnings: List<String>? = null
)

// ==========================================
// 6. مالی و ثبت نام (Financial & Enrollment)
// ==========================================
data class InvoiceSubmitData(
    val student_id: Int,
    val course_id: Int,
    val register_date: String,
    val shift: String,
    val total_tuition: Long,
    val paid_amount: Long,
    val payment_method: String,
    val receiver: String
)

data class SubmitResponse(val message: String, val enrollment_id: Int)

data class InstallmentCreate(
    val amount: Int,
    val due_date: String
)

data class AddStudentToClassData(
    val student_id: Int,
    val course_id: Int,
    val register_date: String,
    val shift: String,
    val total_tuition: Int,
    val paid_amount: Int,
    val payment_method: String,
    val receiver: String,
    val discount_type: String = "none",
    val discount_value: Int = 0,
    val installments: List<InstallmentCreate>? = null
)

data class AddStudentResponse(val message: String, val enrollment_id: Int)

data class BulkEnrollmentData(
    val student_ids: List<Int>,
    val course_id: Int,
    val register_date: String,
    val shift: String,
    val total_tuition: Int,
    val paid_amount: Int,
    val payment_method: String,
    val receiver: String,
    val discount_type: String = "none",
    val discount_value: Int = 0,
    val installments: List<InstallmentCreate>? = null
)

data class BulkEnrollmentRejected(
    val student_id: Int,
    val reason: String
)

data class BulkEnrollmentResponse(
    val message: String,
    val added_count: Int,
    val rejected_count: Int,
    val added_student_ids: List<Int> = emptyList(),
    val rejected: List<BulkEnrollmentRejected> = emptyList()
)

// ==========================================
// 7. حضور و غیاب (Attendance)
// ==========================================
data class AttendanceLogRequest(val course_id: Int, val date: String)
data class AttendanceRecord(val student_id: Int, val name: String, val status: String)
data class AttendanceSubmitItem(val student_id: Int, val status: String, val excused: Boolean = false)
data class AttendanceSubmitData(val course_id: Int, val date: String, val items: List<AttendanceSubmitItem>)
data class AttResponse(val message: String, val present_count: Int)

data class SessionSubmitData(val course_id: Int, val date: String, val items: List<SessionItem>)
data class SessionItem(val student_id: Int, val status: String, val excused: Boolean = false)
data class SessionResponse(
    val message: String, 
    val details: SessionFinancialDetails,
    val session_id: Int? = null,
    val session_code: Int? = null
)
data class SessionFinancialDetails(
    val present_count: Int,
    val cost_per_student: Long,
    val teacher_share: Long,
    val institute_share: Long
)

// ==========================================
// 8. ویرایش پروفایل (Edit Profile)
// ==========================================
data class StudentUpdate(
    val first_name: String? = null,
    val last_name: String? = null,
    val father_name: String? = null,
    val national_code: String? = null,
    val birth_date: String? = null,
    val student_mobile: String? = null,
    val parent_mobile: String? = null,
    val home_phone: String? = null,
    val address: String? = null,
    val study_status: String? = null,
    val gender: String? = null,
    val version: Int? = null
)

data class TeacherUpdate(
    val first_name: String? = null,
    val last_name: String? = null,
    val father_name: String? = null,
    val national_code: String? = null,
    val birth_date: String? = null,
    val mobile: String? = null,
    val home_phone: String? = null,
    val marital_status: String? = null,
    val gender: String? = null,
    val employment_type: String? = null,
    val card_number: String? = null,
    val version: Int? = null
)

data class StudentRawProfile(
    val id: Int,
    val first_name: String,
    val last_name: String,
    val father_name: String?,
    val national_code: String,
    val birth_date: String?,
    val student_mobile: String,
    val parent_mobile: String?,
    val home_phone: String?,
    val address: String?,
    val study_status: String?,
    val gender: String?,
    val student_code: Int? = null,
    val version: Int = 1
)

data class TeacherRawProfile(
    val id: Int,
    // FIX(null-data): رکوردهای legacy ممکن است این چهار فیلد را NULL داشته باشند و
    // پاسخ خام سرور قبلاً null می‌داد — null‌پذیر + فال‌بک امن در پروفایل/فرم ویرایش مربی.
    val first_name: String? = null,
    val last_name: String? = null,
    val father_name: String?,
    val national_code: String? = null,
    val birth_date: String?,
    val mobile: String? = null,
    val home_phone: String?,
    val marital_status: String?,
    val gender: String?,
    val employment_type: String?,
    val card_number: String?,
    val teacher_code: Int? = null,
    val version: Int = 1
)

data class PersonListItem(
    val id: Int,
    // FIX(null-data): فیلدهای legacy (نام/کد ملی/موبایل) ممکن است null باشند —
    // null‌پذیر تا یک رکورد ناقص کل لیست افراد/مربیان را نشکند.
    val name: String? = null,
    val national_code: String? = null,
    val mobile: String? = null,
    val role: String = "",
    val is_suspended: Boolean = false
)

// ==========================================
// مدیریت تراکنش‌ها (Transaction Management)
// ==========================================
data class TransactionFullItem(
    val id: Int,
    val student_id: Int,
    val student_name: String,
    val course_id: Int?,
    val course_name: String,
    val amount: Long,
    val date: String,
    val description: String?,
    val type: String,
    val remittance_number: Int? = null
)

data class TransactionUpdateData(
    val amount: Long,
    val description: String,
    val date: String
)

data class AdvancedSearchItem(
    val type: String,
    val id: Int,
    val title: String,
    val subtitle: String,
    val info: String,
    val student_id: Int? = null,
    val course_id: Int? = null,
    // فیلدهای تفکیک بدهی در سرچ
    val debt_teacher: Long? = 0,
    val debt_institute: Long? = 0,
    val total_debt: Long? = 0,
    val unpaid_sessions: Int? = 0,
    val students_in_class: List<SimpleStudentItem>? = null,
    val enrollment_id: Int? = null,
    val course_title: String? = null,
    val teacher_id: Int? = null,
    val teacher_name: String? = null,
    val is_unassigned: Boolean = false
)

data class SimpleStudentItem(
    val id: Int,
    val name: String,
    val debt: Long,
    @SerializedName("debt_teacher") val debtTeacher: Long = 0,
    @SerializedName("debt_institute") val debtInstitute: Long = 0,
    @SerializedName("total_debt") val totalDebt: Long = 0,
    val enrollment_id: Int? = null,
    val course_id: Int? = null,
    val course_title: String? = null,
    val teacher_id: Int? = null,
    val teacher_name: String? = null,
    val is_unassigned: Boolean = false,
    // «این مبلغ برای چند جلسه است؟» — nullable: null یعنی سرور قدیمی است و این فیلد را نمی‌فرستد
    val course_code: String? = null,
    val sessions_billed: Int? = null,
    val unpaid_sessions: Int? = null
)

// ==========================================
// مدل ثبت مالی جدید
// ==========================================
data class FinanceSubmitData(
    val student_id: Int,
    val amount: Long,
    val target_wallet: String,  // "teacher" یا "institute" یا "both"
    val description: String,
    val payment_method: String,
    val date: String,
    val amount_institute: Long? = null,
    val amount_teacher: Long? = null,
    val enrollment_id: Int? = null,  // اتصال پرداخت به ثبت‌نام؛ null یعنی شارژ عمومی (سرور تک‌ثبت‌نامی را خودکار وصل می‌کند)
    val idempotency_key: String? = null,  // FIX (audit-v2/idempotency): کلید retry — قبل از اولین تلاش ساخته و تا موفقیت حفظ می‌شود
    // تعداد جلسه‌ای که ادمین برایش حواله ثبت می‌کند (اختیاری، فقط گزارشی؛ روی مبلغ اثری ندارد)
    val sessions_covered: Int? = null
)

data class FinanceResponse(
    val message: String,
    val receipt_id: Int,
    val new_balance_teacher: Long,
    val new_balance_institute: Long,
    val duplicate: Boolean = false  // FIX (audit-v2/idempotency): true یعنی replay شد و پرداخت تکراری ثبت نشد
)

// ==========================================
// 9. پروفایل کامل (Full Profile) - ✅ اضافه شد
// ==========================================
// این مدل‌ها برای نمایش پروفایل دانش‌آموز ضروری هستند
data class FullStudentProfile(
    val info: StudentInfo,
    val classes: List<String>,
    // FIX(invoice): enrollmentهای فعال با شناسه‌های واقعی — صدور فیش بدون حدس از نام نمایشی
    // (سرورهای قدیمی بدون این فیلد کار می‌کنند → emptyList)
    val enrollments: List<ActiveStudentEnrollment> = emptyList(),
    val transactions: List<String>,
    @SerializedName("wallet_total") val walletTotal: Long = 0,
    @SerializedName("wallet_teacher") val walletTeacher: Long = 0,
    @SerializedName("wallet_institute") val walletInstitute: Long = 0,
    @SerializedName("total_debt") val totalDebt: Long = 0,
    @SerializedName("debt_teacher") val debtTeacher: Long = 0,
    @SerializedName("debt_institute") val debtInstitute: Long = 0,
    val total_paid_institute: Long = 0,
    val unassigned_debt: Long = 0,
    val teachers_financial: List<TeacherFinancialItem>? = null
)

// FIX(invoice): یک enrollment فعال با شناسه‌های واقعی (نه متن نمایشی)
data class ActiveStudentEnrollment(
    val enrollment_id: Int,
    val course_id: Int,
    val title: String? = null,
    val code: String? = null,
    val branch_id: Int? = null,
    val course_title: String? = null,
    val teacher_id: Int? = null,
    val teacher_name: String? = null,
    val debt: Long? = null,
    val debt_teacher: Long? = null,
    val debt_institute: Long? = null,
    val total_debt: Long? = null,
    val is_unassigned: Boolean = false,
    // بدهی همین کلاس برای چند جلسه است؟ (nullable؛ null = سرور قدیمی)
    val sessions_billed: Int? = null,
    val sessions_held: Int? = null,
    val unpaid_sessions: Int? = null,
    val session_unit_teacher: Long? = null,
    val session_unit_institute: Long? = null,
    val contract_only: Boolean = false
)

data class TeacherFinancialItem(
    val course_title: String? = null,
    val teacher_name: String? = null,
    val paid_teacher: Long,
    val debt_teacher: Long,
    val paid_institute: Long,
    val debt_institute: Long,
    val debt: Long = 0,
    val enrollment_id: Int? = null,
    val course_id: Int? = null,
    val teacher_id: Int? = null,
    val is_unassigned: Boolean = false,
    val course_code: String? = null,
    val sessions_billed: Int? = null,
    val unpaid_sessions: Int? = null,
    val contract_only: Boolean = false
)

data class StudentInfo(
    val name: String,
    val national_code: String,
    val student_mobile: String,
    val parent_mobile: String,
    val address: String,
    val is_suspended: Boolean = false,
    val student_code: Int? = null,
    val profile_image: String? = null
)

// ==========================================
// 12. مدیریت کلاس‌ها (Class Management) - ✅ اضافه شد
// ==========================================
data class ClassListItem(
    val id: Int,
    val title: String,
    val code: String,
    val grade_level: String,
    val gender: String,
    val session_count: Int,
    val teacher_id: Int,
    val teacher_name: String?,
    val students_preview: List<String>,
    val total_debt: Long,
    val debt_to_teacher: Long,
    val debt_to_institute: Long,
    val is_suspended: Boolean = false,
    val bg_color: String? = null,
    val enrollment_id: Int? = null,
    val course_id: Int? = null,
    val course_title: String? = null,
    val is_unassigned: Boolean = false,
    // «بدهی بابت چند جلسهٔ همین کلاس» (nullable: سرور قدیمی نمی‌فرستد ⇒ یادداشت بنر پنهان می‌ماند)
    val unpaid_sessions: Int? = null,
    val sessions_billed: Int? = null
)

// ==========================================
// 13. پروفایل کامل معلم (Full Teacher Profile) - ✅ اضافه شد
// ==========================================
data class TeacherCollaborationSummary(
    @SerializedName("period_days") val periodDays: Int = 30,
    @SerializedName("period_start") val periodStart: String = "",
    @SerializedName("period_end") val periodEnd: String = "",
    @SerializedName("average_delay_minutes") val averageDelayMinutes: Double = 0.0,
    @SerializedName("delay_samples_count") val delaySamplesCount: Int = 0,
    @SerializedName("live_sessions_last_30_days") val liveSessionsLast30Days: Int = 0,
    @SerializedName("total_settlements_count") val totalSettlementsCount: Int = 0,
    @SerializedName("total_settled_amount") val totalSettledAmount: Long = 0,
    @SerializedName("auto_ended_sessions_count") val autoEndedSessionsCount: Int = 0,
    @SerializedName("auto_ended_last_30_days_count") val autoEndedLast30DaysCount: Int = 0
)

data class FullTeacherProfile(
    val info: TeacherInfo,
    val total_students: Int,
    val total_revenue: Long,
    val active_classes_count: Int,
    val classes: List<String>,
    @SerializedName("collaboration_summary") val collaborationSummary: TeacherCollaborationSummary? = null
)

data class TeacherInfo(
    // FIX(null-data): فیلدهای legacy ممکن است null باشند — null‌پذیر + فال‌بک امن در نمایش.
    val name: String? = null,
    val mobile: String? = null,
    val national_code: String? = null,
    val status: String? = null,
    val card_number: String? = null,
    val teacher_code: Int? = null,
    val profile_image: String? = null
)

// ==========================================
// 10. مدل‌های نمرات (Grades) - ✅ اضافه شد
// ==========================================
data class GradeItem(
    @SerializedName("course_name") val courseName: String, // تبدیل course_name سرور به courseName اندروید
    @SerializedName("exam_title") val examTitle: String,
    val score: Float,
    @SerializedName("max_score") val maxScore: Float,
    val date: String,
    val description: String?
)

data class StudentRegisterAndEnrollRequest(
    val first_name: String,
    val last_name: String,
    val father_name: String,
    val national_code: String,
    val birth_date: String,
    val student_mobile: String,
    val parent_mobile: String,
    val home_phone: String,
    val address: String,
    val study_status: String,
    val gender: String,
    val course_id: Int?,
    val total_tuition: Int,
    val paid_amount: Int,
    val payment_method: String,
    val receiver: String,
    val discount_type: String,
    val discount_value: Int,
    val installments: List<InstallmentCreate>? = null
)

data class ParentContactItem(
    val student_id: Int,
    val student_name: String,
    val student_mobile: String,
    val parent_mobile: String,
    val classes: List<String>
)

data class StudentGradesResponse(
    val grades: List<GradeItem>,
    val averages: Map<String, Double>
)

data class GradeSubmitData(
    val student_id: Int,
    val course_id: Int,
    val exam_title: String,
    val score: Float,
    val max_score: Float,
    val date: String,
    val description: String
)

data class SettleRequest(val session_ids: List<Int>)

data class TeacherPendingSettlementResponse(
    val total_amount: Long,
    val session_count: Int,
    val pending_sessions: List<PendingSettlementSession>
)

data class PendingSettlementSession(
    val session_id: Int,
    // FIX(null-data): این فیلدها در داده‌های legacy سرور ممکن است null باشند —
    // null‌پذیر تا یک رکورد ناقص کل RecyclerView تسویه را نشکند.
    val date: String? = null,
    val class_title: String? = null,
    val amount: Long? = null,
    val present_count: Int = 0,
    val session_code: Int? = null
)

data class TeacherSettlementResponse(
    val message: String,
    val settlement_id: Int,
    val total_amount: Long,
    val session_count: Int
)

data class SettlementHistoryItem(
    // Legacy responses expose `id`; new responses also expose the canonical operation key.
    val id: Int,
    val settlement_id: Int? = null,
    // FIX(null-data): مبالغ/تاریخ legacy ممکن است null باشند — null‌پذیر + فال‌بک امن در نمایش.
    val total_amount: Long? = null,
    val session_count: Int = 0,
    val settled_at: String? = null,
    val is_reversed: Boolean = false,
    val reversal_reason: String? = null,
    val session_ids: List<Int>? = null
) {
    // Old cached history remains usable while current responses make the operation
    // identifier explicit. Reverse/edit must never invent a different identifier.
    val operationId: Int
        get() = settlement_id ?: id
}

data class BulkSmsRequest(val student_ids: List<Int>)
data class BulkSuspendRequest(val course_ids: List<Int>)

data class StudentInstallmentItem(
    val id: Int,
    val course_title: String,
    val amount: Long,
    val due_date: String,
    val is_paid: Boolean,
    val paid_at: String,
    @SerializedName("enrollment_id") val enrollmentId: Int? = null,
    @SerializedName("status") val status: String? = null
)

data class CreateInstallmentRequest(
    @SerializedName("enrollment_id") val enrollmentId: Int,
    val amount: Int,
    @SerializedName("due_date") val dueDate: String
)

data class CreateInstallmentResponse(
    val message: String,
    @SerializedName("installment_id") val installmentId: Int
)

data class PayInstallmentResponse(
    val message: String,
    @SerializedName("receipt_id") val receiptId: Int? = null
)

data class RemindInstallmentResponse(
    val status: String,
    val message: String
)

data class WalletInfo(
    val balance: Long = 0,
    @SerializedName("wallet_teacher") val walletTeacher: Long = 0,
    @SerializedName("wallet_institute") val walletInstitute: Long = 0,
    @SerializedName("total_debt") val totalDebt: Long = 0,
    @SerializedName("total_paid") val totalPaid: Long = 0
)

data class DashboardEnrollment(
    @SerializedName("enrollment_id") val enrollmentId: Int,
    @SerializedName("course_id") val courseId: Int? = null,
    @SerializedName("course_title") val courseTitle: String,
    @SerializedName("teacher_id") val teacherId: Int? = null,
    @SerializedName("teacher_name") val teacherName: String? = null,
    @SerializedName("total_tuition") val totalTuition: Long? = null,
    @SerializedName("total_paid") val totalPaid: Long? = null,
    @SerializedName("outstanding") val outstanding: Long? = null,
    @SerializedName("is_unassigned") val isUnassigned: Boolean = false
)

data class FinancialDashboardResponse(
    val wallet: WalletInfo? = null,
    val enrollments: List<DashboardEnrollment> = emptyList(),
    val installments: List<StudentInstallmentItem> = emptyList(),
    @SerializedName("recent_transactions") val recentTransactions: List<TransactionFullItem>? = null
)

data class InstituteSettings(
    val id: Int,
    val name: String,
    val logo_path: String?,
    val address: String,
    val phone: String,
    val official_email: String?,
    val footer_text: String? = null,
    val card_number: String? = null,
    @SerializedName("live_session_max_minutes") val liveSessionMaxMinutes: Int? = null,
    @SerializedName("teacher_settlement_alert_days") val teacherSettlementAlertDays: Int? = null
)

// ==========================================
// 🎥 کلاس‌های زنده (Live Sessions) - جدید 🆕
// ==========================================

// پاسخ شروع کلاس زنده توسط معلم
data class LiveStartResponse(
    val message: String,
    @SerializedName("live_session_id") val liveSessionId: Int,
    @SerializedName("course_id") val courseId: Int,
    val status: String,
    @SerializedName("start_time") val startTime: String?,
    @SerializedName("started_at_ts") val startedAtTs: Long?,
    @SerializedName("max_minutes") val maxMinutes: Int? = null
)

// پاسخ پایان کلاس زنده توسط معلم
data class LiveEndResponse(
    val message: String,
    @SerializedName("live_session_id") val liveSessionId: Int,
    @SerializedName("ended_automatically") val endedAutomatically: Boolean,
    @SerializedName("session_id") val sessionId: Int? = null,
    @SerializedName("session_code") val sessionCode: Int? = null,
    val details: SessionFinancialDetails? = null,
    // FIX (گروه۱/آیتم۱): وقتی جلسهٔ این کلاس در این تاریخ از قبل ثبت شده باشد، سرور کلاس زنده را
    // می‌بندد و به‌جای ۴۰۹ این پرچم + شناسهٔ جلسهٔ موجود را می‌دهد. همه اختیاری با پیش‌فرض ⇒
    // پاسخ سرور قدیمی هم همان‌طور که بود پارس می‌شود (قرارداد نشکسته).
    @SerializedName("duplicate_date") val duplicateDate: Boolean? = null,
    @SerializedName("existing_session_id") val existingSessionId: Int? = null,
    @SerializedName("existing_session_code") val existingSessionCode: Int? = null,
    @SerializedName("duplicate_date_str") val duplicateDateStr: String? = null
)

// پاسخ لغو کلاس زنده؛ لغو هیچ SessionLog یا اثر مالی ایجاد نمی‌کند.
data class LiveCancelResponse(
    val message: String,
    @SerializedName("live_session_id") val liveSessionId: Int,
    val status: String
)

// وضعیت جلسه‌ی زنده‌ی فعلی معلم (برای رزومه و تایمر داشبورد معلم)
data class LiveCurrentResponse(
    @SerializedName("live_session_id") val liveSessionId: Int,
    @SerializedName("course_id") val courseId: Int,
    @SerializedName("class_title") val classTitle: String = "",
    @SerializedName("course_code") val courseCode: String = "",
    val status: String,
    @SerializedName("start_time") val startTime: String?,
    @SerializedName("started_at_ts") val startedAtTs: Long?,
    @SerializedName("max_minutes") val maxMinutes: Int? = null
)

// آیتم لیست کلاس‌های زنده برای ادمین/منشی
data class LiveSessionItem(
    @SerializedName("live_session_id") val liveSessionId: Int,
    @SerializedName("course_id") val courseId: Int,
    @SerializedName("class_title") val classTitle: String = "",
    @SerializedName("course_code") val courseCode: String = "",
    @SerializedName("teacher_name") val teacherName: String = "",
    @SerializedName("start_time") val startTime: String? = null,
    @SerializedName("started_at_ts") val startedAtTs: Long? = null,
    @SerializedName("elapsed_minutes") val elapsedMinutes: Int = 0,
    @SerializedName("total_enrolled") val totalEnrolled: Int = 0,
    val present: Int = 0,
    val absent: Int = 0,
    val undetermined: Int = 0
)

// دانش‌آموز در لیست لحظه‌ای کلاس زنده
data class LiveRosterStudent(
    @SerializedName("student_id") val studentId: Int,
    @SerializedName("student_name") val studentName: String,
    val status: String, // Present / Late / Absent / UNSET
    val excused: Boolean = false,
    @SerializedName("student_mobile") val studentMobile: String = "",
    @SerializedName("parent_mobile") val parentMobile: String = ""
)

// پاسخ کامل جزئیات زنده‌ی یک کلاس (روستر)
data class LiveRosterResponse(
    @SerializedName("live_session_id") val liveSessionId: Int,
    @SerializedName("course_id") val courseId: Int,
    @SerializedName("class_title") val classTitle: String = "",
    @SerializedName("course_code") val courseCode: String = "",
    @SerializedName("teacher_name") val teacherName: String = "",
    @SerializedName("start_time") val startTime: String? = null,
    @SerializedName("started_at_ts") val startedAtTs: Long? = null,
    @SerializedName("elapsed_minutes") val elapsedMinutes: Int = 0,
    @SerializedName("total_enrolled") val totalEnrolled: Int = 0,
    val present: Int = 0,
    val absent: Int = 0,
    val undetermined: Int = 0,
    val students: List<LiveRosterStudent> = emptyList()
)

// ==========================================
// Audit Radar - مدل هشدار تقلب (Read-Only)
// ==========================================
data class AuditAlert(
    val type: String,
    val severity: String, // "high", "medium", "low"
    val title: String,
    val description: String,
    @SerializedName("entity_id") val entityId: Int,
    @SerializedName("entity_name") val entityName: String,
    @SerializedName("detected_at") val detectedAt: String
)

// ==========================================
// Student 360 Timeline - Unified Activity Feed
// ==========================================
data class TimelineEvent(
    val timestamp: String,
    val type: String, // "payment", "absence", "grade", "installment"
    val title: String,
    val subtitle: String,
    @SerializedName("icon_name") val iconName: String,
    @SerializedName("color_hex") val colorHex: String
)

// ==========================================
// Smart Auto-Dunning - Human-in-the-Loop (Admin Only)
// ==========================================
data class DunningDraft(
    @SerializedName("installment_id") val installmentId: Int,
    @SerializedName("student_name") val studentName: String,
    @SerializedName("parent_mobile") val parentMobile: String,
    val amount: Long,
    @SerializedName("due_date") val dueDate: String,
    val category: String, // upcoming | overdue | critical
    @SerializedName("suggested_message") val suggestedMessage: String
)

data class DunningSendRequest(
    @SerializedName("installment_ids") val installmentIds: List<Int>
)

data class DunningSendResponse(
    @SerializedName("sent_count") val sentCount: Int,
    @SerializedName("skipped_count") val skippedCount: Int,
    @SerializedName("sent_ids") val sentIds: List<Int>,
    @SerializedName("skipped_ids") val skippedIds: List<Int>,
    val message: String,
    @SerializedName("skipped_reasons") val skippedReasons: Map<String, String>? = null
)

// ==========================================
// Admin Command Center - Unified Dashboard (Admin Only)
// ==========================================
data class DashboardKPIs(
    @SerializedName("today_revenue") val todayRevenue: Long,
    @SerializedName("total_overdue_amount") val totalOverdueAmount: Long,
    @SerializedName("overdue_installments_count") val overdueInstallmentsCount: Int,
    @SerializedName("active_students_count") val activeStudentsCount: Int,
    @SerializedName("suspicious_alerts_count") val suspiciousAlertsCount: Int,
    @SerializedName("dunning_pending_count") val dunningPendingCount: Int
)

// ==========================================
// Financial Audit Trail — ردگیری تغییرات مالی (admin only)
// ==========================================
data class AuditTrailLog(
    val id: Int,
    val timestamp: String,
    val username: String? = null,
    val action: String,                       // create | update | delete
    @SerializedName("entity_type") val entityType: String,   // transaction | installment
    @SerializedName("entity_id") val entityId: Int? = null,
    @SerializedName("old_values") val oldValues: Map<String, Any>? = null,
    @SerializedName("new_values") val newValues: Map<String, Any>? = null,
    @SerializedName("ip_address") val ipAddress: String? = null,
    @SerializedName("changed_fields") val changedFields: List<String> = emptyList(),
    // ---- FIX (گروه۲/آیتم۸): فیلدهای غنی‌شده‌ی سرور (همه اختیاری ⇒ کلاینت قدیمی نمی‌شکند) ----
    /** نام ستون → برچسب فارسی (فقط ستون‌های تغییریافته) */
    val labels: Map<String, String>? = null,
    @SerializedName("changed_labels") val changedLabels: List<String>? = null,
    /** جمله‌ی خوانا: «مبلغ: 100,000 ← 250,000» */
    @SerializedName("change_summary") val changeSummary: String? = null,
    @SerializedName("action_label") val actionLabel: String? = null,
    /** new_payment | edited | reversed | voided | deleted */
    @SerializedName("change_type") val changeType: String? = null,
    @SerializedName("action_color") val actionColor: String? = null,
    @SerializedName("icon_color") val iconColor: String? = null,
    /** نام‌ها به‌جای شناسه‌ی خام: student/teacher/course/branch/enrollment */
    @SerializedName("entity_refs") val entityRefs: Map<String, String>? = null,
    @SerializedName("student_id") val studentId: Int? = null,
    @SerializedName("student_name") val studentName: String? = null,
    @SerializedName("student_statement_path") val studentStatementPath: String? = null,
    @SerializedName("actor_username") val actorUsername: String? = null,
    /** audit_context | activity_log | none */
    @SerializedName("actor_source") val actorSource: String? = null,
    @SerializedName("actor_action") val actorAction: String? = null,
    @SerializedName("actor_action_key") val actorActionKey: String? = null
)

data class AuditTrailResponse(
    val logs: List<AuditTrailLog>,
    val total: Int,
    val page: Int,
    val limit: Int,
    val pages: Int
)
