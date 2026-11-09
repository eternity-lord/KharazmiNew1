package com.example.kharazmiadmin

import android.content.Context
import android.os.Bundle
import android.view.View
import android.widget.Button
import android.widget.TextView
import android.widget.Toast
import androidx.lifecycle.lifecycleScope
import com.github.mikephil.charting.charts.BarChart
import com.github.mikephil.charting.charts.LineChart
import com.github.mikephil.charting.charts.PieChart
import com.github.mikephil.charting.components.XAxis
import com.github.mikephil.charting.data.BarData
import com.github.mikephil.charting.data.BarDataSet
import com.github.mikephil.charting.data.BarEntry
import com.github.mikephil.charting.data.Entry
import com.github.mikephil.charting.data.LineData
import com.github.mikephil.charting.data.LineDataSet
import com.github.mikephil.charting.data.PieData
import com.github.mikephil.charting.data.PieDataSet
import com.github.mikephil.charting.data.PieEntry
import com.github.mikephil.charting.formatter.IndexAxisValueFormatter
import com.github.mikephil.charting.formatter.ValueFormatter
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import retrofit2.http.GET
import retrofit2.http.Query
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Locale

// ۱. ساختار پویای مدل پاسخ برای چارت‌های جدید
data class ChartDataResponse(
    val income_chart: List<IncomeData>,
    val student_chart: List<StudentStat>,
    val attendance_trend: List<AttendanceTrendItem>?,
    val shares_chart: SharesData?
)

data class IncomeData(val day: String, val amount: Float)
data class StudentStat(val label: String, val count: Float)

data class AttendanceTrendItem(
    val date: String,
    val present: Int,
    val absent: Int,
    val percentage: Double
)

data class SharesData(
    val teacher: Long,
    val institute: Long
)

data class FunnelPeriod(
    val start_date: String,
    val end_date: String
)

data class EnrollmentFunnelResponse(
    val period: FunnelPeriod,
    val branch_id: Int,
    val total_leads: Int,
    val converted_leads: Int,
    val conversion_rate: Double,
    val average_conversion_hours: Double,
    val average_conversion_days: Double,
    val timed_conversions: Int
)

interface ChartApi {
    @GET("reports/chart-data")
    suspend fun getChartData(
        @Query("class_id") classId: Int?,
        @Query("start_date") startDate: String?,
        @Query("end_date") endDate: String?
    ): ChartDataResponse

    @GET("analytics/enrollment_funnel")
    suspend fun getEnrollmentFunnel(
        @Query("start_date") startDate: String,
        @Query("end_date") endDate: String,
        @Query("branch_id") branchId: Int
    ): EnrollmentFunnelResponse
}

class ChartActivity : BaseActivity() {

    private var classId: Int = -1
    private lateinit var api: ChartApi
    private var isAdmin: Boolean = false
    private var branchId: Int = 1

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_chart)

        val prefs = getSharedPreferences("UserCreds", Context.MODE_PRIVATE)
        isAdmin = (prefs.getString("USER_SUB_ROLE", "admin") ?: "admin") == "admin"
        branchId = intent.getIntExtra(
            "BRANCH_ID",
            prefs.getInt("USER_BRANCH_ID", 1)
        )
        findViewById<View>(R.id.cardEnrollmentFunnel).visibility =
            if (isAdmin) View.VISIBLE else View.GONE

        // دریافت آی‌دی کلاس اختیاری در صورتی که از جزئیات کلاس آمده باشیم
        classId = intent.getIntExtra("CLASS_ID", -1)
        val className = intent.getStringExtra("CLASS_NAME")

        if (classId != -1) {
            findViewById<TextView>(R.id.tvAttendanceChartTitle)?.text = getString(R.string.chart_att_title, className ?: "")
        }

        val retrofit = RetrofitClient.getInstance(this)
        api = retrofit.create(ChartApi::class.java)

        // فیلترهای بالا
        findViewById<Button>(R.id.btnFilterWeek).setOnClickListener {
            loadAnalyticsForRange(7)
        }
        findViewById<Button>(R.id.btnFilterMonth).setOnClickListener {
            loadAnalyticsForRange(30)
        }
        findViewById<Button>(R.id.btnFilterQuarter).setOnClickListener {
            loadAnalyticsForRange(90)
        }

        // بارگذاری اولیه چارت‌ها با فیلتر ماه اخیر
        loadAnalyticsForRange(30)
    }

    private fun loadAnalyticsForRange(daysAgo: Int) {
        // Keep the existing chart API's date convention untouched.
        loadChartData(getPastDateString(daysAgo), getTodayDateString())
        if (isAdmin) {
            loadEnrollmentFunnel(
                getGregorianDateString(daysAgo),
                getGregorianDateString(0)
            )
        }
    }

    private fun loadEnrollmentFunnel(startDate: String, endDate: String) {
        findViewById<TextView>(R.id.tvFunnelAverage).text = getString(R.string.chart_funnel_loading)
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val funnel = api.getEnrollmentFunnel(startDate, endDate, branchId)
                withContext(Dispatchers.Main) {
                    findViewById<TextView>(R.id.tvFunnelTotal).text =
                        funnel.total_leads.toString()
                    findViewById<TextView>(R.id.tvFunnelConverted).text =
                        funnel.converted_leads.toString()
                    findViewById<TextView>(R.id.tvFunnelRate).text =
                        String.format(Locale.US, "%.2f%%", funnel.conversion_rate)
                    findViewById<TextView>(R.id.tvFunnelAverage).text =
                        when {
                            funnel.timed_conversions == 0 ->
                                getString(R.string.chart_conv_none)
                            funnel.average_conversion_hours < 24.0 ->
                                getString(R.string.chart_conv_hours, String.format(Locale.US, "%.1f", funnel.average_conversion_hours))
                            else ->
                                getString(R.string.chart_conv_days, String.format(Locale.US, "%.1f", funnel.average_conversion_days))
                        }
                    setupEnrollmentFunnelChart(funnel)
                }
            } catch (ignoredError: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (ignoredError is kotlinx.coroutines.CancellationException) throw ignoredError;
                withContext(Dispatchers.Main) {
                    findViewById<TextView>(R.id.tvFunnelAverage).text =
                        getString(R.string.chart_funnel_error)
                }
            }
        }
    }

    private fun setupEnrollmentFunnelChart(data: EnrollmentFunnelResponse) {
        val chart = findViewById<BarChart>(R.id.enrollmentFunnelChart)
        val entries = arrayListOf(
            BarEntry(0f, data.total_leads.toFloat()),
            BarEntry(1f, data.converted_leads.toFloat())
        )
        val dataSet = BarDataSet(entries, getString(R.string.chart_ds_count))
        dataSet.colors = listOf(
            UiColors.resolve(this@ChartActivity, R.color.status_info),
            UiColors.resolve(this@ChartActivity, R.color.gaj_green_dark)
        )
        dataSet.valueTextSize = 12f
        dataSet.valueTextColor = UiColors.resolve(this@ChartActivity, R.color.ds_text_primary)
        dataSet.valueFormatter = object : ValueFormatter() {
            override fun getFormattedValue(value: Float): String = value.toInt().toString()
        }

        chart.data = BarData(dataSet).apply { barWidth = 0.55f }
        chart.description.isEnabled = false
        chart.setNoDataText(getString(R.string.chart_no_data))
        chart.setNoDataTextColor(UiColors.resolve(this@ChartActivity, R.color.ds_text_secondary))
        chart.legend.isEnabled = false
        chart.axisRight.isEnabled = false
        chart.axisLeft.axisMinimum = 0f
        chart.axisLeft.textColor = UiColors.resolve(this@ChartActivity, R.color.ds_text_secondary)
        chart.xAxis.textColor = UiColors.resolve(this@ChartActivity, R.color.ds_text_secondary)
        chart.xAxis.valueFormatter =
            IndexAxisValueFormatter(listOf(getString(R.string.chart_funnel_in), getString(R.string.chart_funnel_done)))
        chart.xAxis.position = XAxis.XAxisPosition.BOTTOM
        chart.xAxis.granularity = 1f
        chart.xAxis.setDrawGridLines(false)
        chart.setFitBars(true)
        chart.animateY(700)
        chart.invalidate()
    }

    private fun getGregorianDateString(daysAgo: Int): String {
        val calendar = Calendar.getInstance()
        calendar.add(Calendar.DAY_OF_YEAR, -daysAgo)
        return SimpleDateFormat("yyyy/MM/dd", Locale.US).format(calendar.time)
    }

    private fun loadChartData(startDate: String, endDate: String) {
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                // ارسال درخواست فیلتر شده به سرور همراه class_id و بازه زمانی
                val queryClassId = if (classId != -1) classId else null
                val data = api.getChartData(queryClassId, startDate, endDate)

                withContext(Dispatchers.Main) {
                    setupBarChart(data.income_chart)
                    setupPieChart(data.student_chart)
                    
                    // رسم چارت ۱: روند حضور و غیاب
                    if (!data.attendance_trend.isNullOrEmpty()) {
                        findViewById<View>(R.id.attendanceLineChart)?.visibility = View.VISIBLE
                        setupAttendanceLineChart(data.attendance_trend)
                    } else {
                        findViewById<View>(R.id.attendanceLineChart)?.visibility = View.INVISIBLE
                        Toast.makeText(this@ChartActivity, getString(R.string.chart_att_empty), Toast.LENGTH_SHORT).show()
                    }

                    // رسم چارت ۲: سهم وصولی معلم و آموزشگاه
                    if (data.shares_chart != null && (data.shares_chart.teacher > 0 || data.shares_chart.institute > 0)) {
                        findViewById<View>(R.id.sharesPieChart)?.visibility = View.VISIBLE
                        setupSharesPieChart(data.shares_chart)
                    } else {
                        findViewById<View>(R.id.sharesPieChart)?.visibility = View.INVISIBLE
                        Toast.makeText(this@ChartActivity, getString(R.string.chart_money_empty), Toast.LENGTH_SHORT).show()
                    }
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@ChartActivity, getString(R.string.chart_stats_error), Toast.LENGTH_SHORT).show()
                    android.util.Log.e("ChartActivity", "loadChartData failed", e)
                }
            }
        }
    }

    // نمودار میله‌ای روند درآمد
    private fun setupBarChart(data: List<IncomeData>) {
        val barChart = findViewById<BarChart>(R.id.barChart) ?: return

        val entries = ArrayList<BarEntry>()
        val labels = ArrayList<String>()

        for (i in data.indices) {
            entries.add(BarEntry(i.toFloat(), data[i].amount))
            labels.add(data[i].day)
        }

        val dataSet = BarDataSet(entries, getString(R.string.chart_ds_income))
        dataSet.color = UiColors.resolve(this@ChartActivity, R.color.gaj_green_dark) // رنگ سبز گاج
        dataSet.valueTextSize = 11f
        dataSet.valueTextColor = UiColors.resolve(this@ChartActivity, R.color.ds_text_primary)

        val barData = BarData(dataSet)
        barChart.data = barData

        barChart.description.isEnabled = false
        barChart.setNoDataText(getString(R.string.chart_no_data))
        barChart.setNoDataTextColor(UiColors.resolve(this@ChartActivity, R.color.ds_text_secondary))
        barChart.axisLeft.textColor = UiColors.resolve(this@ChartActivity, R.color.ds_text_secondary)
        barChart.xAxis.textColor = UiColors.resolve(this@ChartActivity, R.color.ds_text_secondary)
        barChart.legend.textColor = UiColors.resolve(this@ChartActivity, R.color.ds_text_secondary)
        barChart.xAxis.valueFormatter = IndexAxisValueFormatter(labels)
        barChart.xAxis.position = XAxis.XAxisPosition.BOTTOM
        barChart.xAxis.granularity = 1f
        barChart.animateY(1000)
        barChart.invalidate()
    }

    // نمودار دایره‌ای تفکیک جنسیت
    private fun setupPieChart(data: List<StudentStat>) {
        val pieChart = findViewById<PieChart>(R.id.pieChart) ?: return

        val entries = ArrayList<PieEntry>()
        for (item in data) {
            if (item.count > 0)
                entries.add(PieEntry(item.count, item.label))
        }

        val dataSet = PieDataSet(entries, "")
        dataSet.colors = listOf(
            UiColors.resolve(this@ChartActivity, R.color.gaj_green_dark), // سبز تیره گاج
            UiColors.resolve(this@ChartActivity, R.color.gaj_accent), // زرد طلایی
            UiColors.resolve(this@ChartActivity, R.color.status_danger)  // قرمز
        )
        dataSet.valueTextSize = 14f
        dataSet.valueTextColor = UiColors.resolve(this@ChartActivity, R.color.white)

        val pieData = PieData(dataSet)
        pieChart.data = pieData

        pieChart.description.isEnabled = false
        pieChart.setNoDataText(getString(R.string.chart_no_data))
        pieChart.setNoDataTextColor(UiColors.resolve(this@ChartActivity, R.color.ds_text_secondary))
        pieChart.setCenterTextColor(UiColors.resolve(this@ChartActivity, R.color.ds_text_primary))
        pieChart.setEntryLabelColor(UiColors.resolve(this@ChartActivity, R.color.ds_text_primary))
        pieChart.legend.textColor = UiColors.resolve(this@ChartActivity, R.color.ds_text_secondary)
        pieChart.centerText = getString(R.string.chart_pie_all)
        pieChart.setCenterTextSize(15f)
        pieChart.animateY(1000)
        pieChart.invalidate()
    }

    // نمودار خطی روند حضور و غیاب دانش‌آموزان (چارت جدید ۱)
    private fun setupAttendanceLineChart(data: List<AttendanceTrendItem>) {
        val lineChart = findViewById<LineChart>(R.id.attendanceLineChart) ?: return

        val entries = ArrayList<Entry>()
        val labels = ArrayList<String>()

        val unknownDate = getString(R.string.chart_date_unknown)
        for (i in data.indices) {
            entries.add(Entry(i.toFloat(), data[i].percentage.toFloat()))
            // FIX(A3): سرور برای جلسه‌ی بدون تاریخ "" برمی‌گرداند (هیچ تاریخ جعلی ساخته نمی‌شود)
            // ⇒ به‌جای برچسب خالی، «تاریخ نامشخص» روی محور نمایش داده می‌شود.
            labels.add(data[i].date.takeIf { it.isNotBlank() } ?: unknownDate)
        }

        val dataSet = LineDataSet(entries, getString(R.string.chart_line_att))
        dataSet.color = UiColors.resolve(this@ChartActivity, R.color.gaj_green_dark) // رنگ سبز اصلی
        dataSet.setCircleColor(UiColors.resolve(this@ChartActivity, R.color.gaj_accent)) // زرد طلایی
        dataSet.lineWidth = 3f
        dataSet.circleRadius = 5f
        dataSet.setDrawCircleHole(true)
        dataSet.valueTextSize = 11f
        dataSet.valueTextColor = UiColors.resolve(this@ChartActivity, R.color.text_primary)
        dataSet.setDrawFilled(true)
        dataSet.fillColor = UiColors.resolve(this@ChartActivity, R.color.status_success_light) // رنگ سبز ملایم پشت خط

        val lineData = LineData(dataSet)
        lineChart.data = lineData

        lineChart.description.isEnabled = false
        lineChart.setNoDataText(getString(R.string.chart_no_data))
        lineChart.setNoDataTextColor(UiColors.resolve(this@ChartActivity, R.color.ds_text_secondary))
        lineChart.axisLeft.textColor = UiColors.resolve(this@ChartActivity, R.color.ds_text_secondary)
        lineChart.xAxis.textColor = UiColors.resolve(this@ChartActivity, R.color.ds_text_secondary)
        lineChart.legend.textColor = UiColors.resolve(this@ChartActivity, R.color.ds_text_secondary)
        lineChart.xAxis.valueFormatter = IndexAxisValueFormatter(labels)
        lineChart.xAxis.position = XAxis.XAxisPosition.BOTTOM
        lineChart.xAxis.granularity = 1f
        lineChart.animateY(1000)
        lineChart.invalidate()
    }

    // نمودار دایره‌ای سهم معلم در برابر آموزشگاه (چارت جدید ۲)
    private fun setupSharesPieChart(data: SharesData) {
        val pieChart = findViewById<PieChart>(R.id.sharesPieChart) ?: return

        val entries = ArrayList<PieEntry>()
        if (data.teacher > 0) {
            entries.add(PieEntry(data.teacher.toFloat(), getString(R.string.chart_pie_teacher)))
        }
        if (data.institute > 0) {
            entries.add(PieEntry(data.institute.toFloat(), getString(R.string.chart_pie_institute)))
        }

        val dataSet = PieDataSet(entries, "")
        dataSet.colors = listOf(
            UiColors.resolve(this@ChartActivity, R.color.gaj_green_dark), // سبز تیره گاج
            UiColors.resolve(this@ChartActivity, R.color.gaj_accent)  // زرد طلایی گاج
        )
        dataSet.valueTextSize = 13f
        dataSet.valueTextColor = UiColors.resolve(this@ChartActivity, R.color.white)

        val pieData = PieData(dataSet)
        pieChart.data = pieData

        pieChart.description.isEnabled = false
        pieChart.setNoDataText(getString(R.string.chart_no_data))
        pieChart.setNoDataTextColor(UiColors.resolve(this@ChartActivity, R.color.ds_text_secondary))
        pieChart.setCenterTextColor(UiColors.resolve(this@ChartActivity, R.color.ds_text_primary))
        pieChart.setEntryLabelColor(UiColors.resolve(this@ChartActivity, R.color.ds_text_primary))
        pieChart.legend.textColor = UiColors.resolve(this@ChartActivity, R.color.ds_text_secondary)
        pieChart.centerText = getString(R.string.chart_pie_collected)
        pieChart.setCenterTextSize(15f)
        pieChart.animateY(1000)
        pieChart.invalidate()
    }

    // FIX H3-B2: real Jalali ranges for the server (was year-621 approximation).
    private fun getPastDateString(daysAgo: Int): String {
        return JalaliUtils.jalaliStringDaysAgo(daysAgo)
    }

    private fun getTodayDateString(): String {
        return JalaliUtils.todayJalaliString()
    }
}
