package com.example.kharazmiadmin

// این کلاس‌ها دقیقاً با خروجی JSON سرور که ساختیم هماهنگ هستن
data class DashboardResponse(
    val student_count: Int,
    val class_count: Int,
    val last_transaction: TransactionInfo?,
    val last_course: CourseInfo?
)

data class TransactionInfo(
    val student_name: String,
    val amount: Long,
    val date: String
)

data class CourseInfo(
    val title: String,
    val code: String,
    val teacher: String,
    val grade: String
)
