package com.example.kharazmiadmin.ui

/**
 * ⚡ سناریوی کاربری محاسبات هوشمند داشبورد (Dashboard Calculation UseCase)
 * مسئول فیلترینگ منطقی و تبدیل داده‌های خام خام به ساختار ریسپانسیو و تمیز قبل از نمایش در UI.
 */
class GetDashboardStatsUseCase(private val repository: MainRepository) {

    /**
     * اجرای منطق بیزینس و محاسبات تراز مالی شعب
     */
    suspend fun execute(branchId: Int? = null): DashboardUiState {
        val rawStats = repository.fetchBranchStats(branchId)
        
        val studentCount = rawStats["student_count"] as? Long ?: 0L
        val classCount = rawStats["class_count"] as? Long ?: 0L
        val totalRevenue = rawStats["total_revenue"] as? Long ?: 0L
        val sessionsCount = rawStats["attendance_sessions"] as? Long ?: 0L

        // فرمول بیزینس: نسبت تعداد دانش‌آموزان به کلاس‌ها جهت نمایش توزیع تراکم کلاس
        val density = if (classCount > 0) studentCount.toFloat() / classCount else 0f

        return DashboardUiState.Success(
            studentCount = studentCount,
            classCount = classCount,
            totalRevenue = totalRevenue,
            sessionsCount = sessionsCount,
            classDensity = density
        )
    }
}

/**
 * وضعیت‌های مختلف بارگذاری داده در صفحه (MVI/MVVM State Pattern)
 */
sealed class DashboardUiState {
    object Loading : DashboardUiState()
    data class Success(
        val studentCount: Long,
        val classCount: Long,
        val totalRevenue: Long,
        val sessionsCount: Long,
        val classDensity: Float
    ) : DashboardUiState()
    data class Error(val errorMessage: String) : DashboardUiState()
}
