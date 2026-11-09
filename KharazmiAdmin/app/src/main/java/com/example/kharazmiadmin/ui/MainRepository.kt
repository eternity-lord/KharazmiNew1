package com.example.kharazmiadmin.ui

import com.example.kharazmiadmin.StudentClassStatus
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * 📊 مخزن داده اصلی بخش مدیریت و داشبوردها (Main & Dashboard Repository)
 * این کلاس وظیفه انتزاع شبکه و فرآیند واکشی اطلاعات آماری از سرور خوارزمی را به عهده دارد.
 */
class MainRepository(private val api: ClassStatusApi) {

    /**
     * دریافت آمار شعب به تفکیک یا کلی جهت رندر روی نمودارها
     */
    suspend fun fetchBranchStats(branchId: Int? = null): Map<String, Any> = withContext(Dispatchers.IO) {
        // شبیه‌سازی دریافت اطلاعات شعبه از سرور بک‌اند مجهز به چندشعبه‌ای
        try {
            // در پیاده‌سازی واقعی از رتروفیت استفاده می‌شود:
            // return api.getBranchStats(branchId)
            mapOf(
                "student_count" to 142L,
                "class_count" to 12L,
                "total_revenue" to 12500000L,
                "attendance_sessions" to 45L
            )
        } catch (e: Exception) {
            emptyMap()
        }
    }

    /**
     * واکشی وضعیت بدهی کلاس دانش‌آموز به صورت کاملاً ایمن
     */
    suspend fun getStudentClassStatus(studentId: Int, courseId: Int?, courseCode: String?): StudentClassStatus {
        return api.getStudentClassStatus(studentId, courseId, courseCode)
    }
}

// طرح‌واره تکمیلی ClassStatusApi جهت انطباق رتروفیت
// FIX L6: rename — این انتزاع تک‌متده ربطی به NewInvoiceApi رتروفیت (ApiInterfaces) ندارد؛ هم‌نامی سایه می‌ساخت.
interface ClassStatusApi {
    suspend fun getStudentClassStatus(studentId: Int, courseId: Int?, courseCode: String?): StudentClassStatus
}
