package com.example.kharazmiadmin.ui

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/**
 * 📱 مدل‌نمای مدیریت داشبوردها (Dashboard ViewModel)
 * پیاده‌سازی معماری MVVM جهت جداسازی لایه Business Logic از Activityهای سنگین اندروید.
 */
class MainViewModel(
    private val getDashboardStatsUseCase: GetDashboardStatsUseCase
) {
    // استفاده از StateFlow برای همگام‌سازی داینامیک کاتلین و جت‌پک کامپوز
    private val _uiState = MutableStateFlow<DashboardUiState>(DashboardUiState.Loading)
    val uiState: StateFlow<DashboardUiState> = _uiState.asStateFlow()

    private val _selectedBranchId = MutableStateFlow<Int?>(null)
    val selectedBranchId: StateFlow<Int?> = _selectedBranchId.asStateFlow()

    /**
     * واکشی اطلاعات آماری با اعمال فیلتر شعبه انتخابی ادمین
     */
    fun loadDashboardStats(branchId: Int? = null) {
        _uiState.value = DashboardUiState.Loading
        _selectedBranchId.value = branchId
        
        // در اندروید واقعی از viewModelScope.launch استفاده می‌شود:
        // viewModelScope.launch {
        //     try {
        //         val state = getDashboardStatsUseCase.execute(branchId)
        //         _uiState.value = state
        //     } catch (e: Exception) {
        //         _uiState.value = DashboardUiState.Error("خطا در برقراری ارتباط با سرور خوارزمی")
        //     }
        // }
        
        // شبیه‌سازی لود موفقیت‌آمیز داده‌ها
        _uiState.value = DashboardUiState.Success(
            studentCount = 142L,
            classCount = 12L,
            totalRevenue = 12500000L,
            sessionsCount = 45L,
            classDensity = 11.8f
        )
    }

    /**
     * تغییر دستی شعبه فعال از فیلتر بالای صفحه
     */
    fun selectBranch(branchId: Int?) {
        loadDashboardStats(branchId)
    }
}
