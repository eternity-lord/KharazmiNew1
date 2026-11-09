package com.example.kharazmiadmin

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.text.Editable
import android.text.TextWatcher
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import android.widget.Toast
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.google.android.material.button.MaterialButton
import com.google.android.material.textfield.TextInputEditText
import kotlinx.coroutines.*
import retrofit2.http.GET
import retrofit2.http.Query

interface AdminListApi {
    @GET("admin/students/search")
    suspend fun getStudents(@Query("query") q: String?): List<PersonListItem>

    @GET("admin/teachers/search")
    suspend fun getTeachers(@Query("query") q: String?): List<PersonListItem>
}

class PersonListActivity : BaseActivity() {

    private lateinit var rv: RecyclerView
    private lateinit var etSearch: TextInputEditText
    private lateinit var api: AdminListApi
    private var mode: String = "STUDENT" // "STUDENT" or "TEACHER"
    // FIX: Bugs 19/21 - a testable latest-request controller owned by this Activity lifecycle.
    private val searchRequests by lazy { DebouncedRequest(lifecycleScope) }
    private var currentList: List<PersonListItem> = emptyList()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_person_list)

        mode = intent.getStringExtra("MODE") ?: "STUDENT"

        // تنظیم عنوان صفحه
        val title = if (mode == "STUDENT") getString(R.string.plist_title_students) else getString(R.string.plist_title_teachers)
        findViewById<TextView>(R.id.tvHeaderTitle).text = title

        rv = findViewById(R.id.rvList)
        etSearch = findViewById(R.id.etSearch)
        rv.layoutManager = LinearLayoutManager(this)

        val retrofit = RetrofitClient.getInstance(this)
        api = retrofit.create(AdminListApi::class.java)

        // مدیریت پنل خروجی اکسل/PDF برای معلمان
        if (mode == "TEACHER") {
            findViewById<View>(R.id.llPersonExportContainer).visibility = View.VISIBLE
            
            // دکمه خروجی اکسل معلمان
            findViewById<MaterialButton>(R.id.btnPersonExportExcel).setOnClickListener {
                ReportExporter.exportToExcel(
                    context = this,
                    endpointUrl = "teachers/list/excel",
                    fileName = "teachers_list.xlsx",
                    onStart = {
                        Toast.makeText(this, getString(R.string.plist_excel_start), Toast.LENGTH_SHORT).show()
                    },
                    onComplete = {
                        Toast.makeText(this, getString(R.string.plist_excel_done), Toast.LENGTH_SHORT).show()
                    },
                    onError = { errorMsg ->
                        Toast.makeText(this, getString(R.string.plist_excel_error, errorMsg), Toast.LENGTH_LONG).show()
                    }
                )
            }

            // دکمه چاپ PDF معلمان
            findViewById<MaterialButton>(R.id.btnPersonExportPdf).setOnClickListener {
                if (currentList.isEmpty()) {
                    Toast.makeText(this, getString(R.string.plist_print_empty), Toast.LENGTH_SHORT).show()
                    return@setOnClickListener
                }

                val headers = listOf(getString(R.string.common_id), getString(R.string.plist_th_name), getString(R.string.plist_th_national), getString(R.string.plist_th_mobile))
                val rows = currentList.map { item ->
                    listOf(
                        item.id.toString(),
                        item.name ?: "",
                        item.national_code ?: "",
                        item.mobile ?: ""
                    )
                }

                ReportExporter.printPdfReport(
                    context = this,
                    title = getString(R.string.plist_report_title),
                    headers = headers,
                    rows = rows
                )
            }
        }

        val swipeRefreshLayout = findViewById<androidx.swiperefreshlayout.widget.SwipeRefreshLayout>(R.id.swipeRefreshLayout)
        swipeRefreshLayout.setOnRefreshListener {
            val query = etSearch.text.toString().trim()
            val cacheKey = "person_list_" + mode + "_" + query
            CacheManager.clear(this, cacheKey) // ابطال کش محلی جهت لود اجباری از سرور
            fetchData(query)
            swipeRefreshLayout.isRefreshing = false
        }

        // دریافت لیست اولیه
        fetchData("")

        // سرچ زنده
        etSearch.addTextChangedListener(object : TextWatcher {
            override fun afterTextChanged(s: Editable?) {
                // FIX: Bug 21 - capture immutable text and cancel the previous debounce/request together.
                fetchData(s?.toString().orEmpty().trim(), debounce = true)
            }
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {}
        })
    }

    private fun fetchData(query: String, debounce: Boolean = false) {
        // FIX: Bug 21 - initial load, refresh and typing share one job; stale responses cannot replace newer results.
        val cacheKey = "person_list_" + mode + "_" + query
        val type = object : com.google.gson.reflect.TypeToken<List<PersonListItem>>() {}.type

        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.

        // FIX: Bug 21 - the controller owns both the 400 ms delay and the network call.
        searchRequests.submit(debounce) {
            CachedApiCall.execute(
                context = this@PersonListActivity,
                cacheKey = cacheKey,
                type = type,
                networkCall = {
                    if (mode == "STUDENT") {
                        api.getStudents(query)
                    } else {
                        api.getTeachers(query)
                    }
                },
                onSuccess = { list, isOffline, timestamp ->
                    currentList = list
                    if (list.isEmpty()) {
                        val roleText = if (mode == "STUDENT") getString(R.string.classes_students) else getString(R.string.plist_tutor)
                        Toast.makeText(this@PersonListActivity, getString(R.string.plist_empty_row, roleText), Toast.LENGTH_LONG).show()
                    }
                    if (mode == "TEACHER") {
                        rv.adapter = ImprovedTeacherAdapter(list)
                    } else {
                        rv.adapter = PersonAdapter(list, mode)
                    }
                    if (isOffline) {
                        CachedApiCall.showOfflineBanner(this@PersonListActivity, timestamp)
                    } else {
                        CachedApiCall.hideOfflineBanner(this@PersonListActivity)
                    }
                },
                onFailure = {
                    Toast.makeText(this@PersonListActivity, getString(R.string.common_offline_empty), Toast.LENGTH_LONG).show()
                }
            )
        }
    }
}

// آداپتور لیست
class PersonAdapter(private val list: List<PersonListItem>, private val mode: String) : RecyclerView.Adapter<PersonAdapter.VH>() {

    class VH(v: View) : RecyclerView.ViewHolder(v) {
        val tvName: TextView = v.findViewById(R.id.tvName)
        val tvCode: TextView = v.findViewById(R.id.tvCode)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val v = LayoutInflater.from(parent.context).inflate(R.layout.item_person_row, parent, false)
        return VH(v)
    }

    override fun onBindViewHolder(holder: VH, position: Int) {
        val item = list[position]
        // FIX(null-data): نام/کد ملی/موبایل legacy ممکن است null باشند — فال‌بک امن + تله‌ی نهایی.
        try {
            holder.tvName.text = item.name ?: ""
            holder.tvCode.text = holder.itemView.context.getString(R.string.plist_code_mobile, item.national_code ?: "", item.mobile ?: "")
        } catch (e: Exception) {
            android.util.Log.e("PersonAdapter", "Error binding row ${item.id}", e)
        }

        holder.itemView.setOnClickListener {
            val context = holder.itemView.context
            if (mode == "STUDENT") {
                val intent = Intent(context, StudentProfileActivity::class.java)
                intent.putExtra("STUDENT_ID", item.id)
                context.startActivity(intent)
            } else {
                val intent = Intent(context, TeacherProfileActivity::class.java)
                intent.putExtra("TEACHER_ID", item.id)
                context.startActivity(intent)
            }
        }
    }

    override fun getItemCount() = list.size
}

// آداپتور بهبود یافته برای معلمان
class ImprovedTeacherAdapter(private val list: List<PersonListItem>) : RecyclerView.Adapter<ImprovedTeacherAdapter.TeacherViewHolder>() {

    class TeacherViewHolder(view: View) : RecyclerView.ViewHolder(view) {
        val tvTeacherName: TextView = view.findViewById(R.id.tvTeacherName)
        val tvTeacherMobile: TextView = view.findViewById(R.id.tvTeacherMobile)
        val tvTeacherStatus: TextView = view.findViewById(R.id.tvTeacherStatus)
        val tvNationalCode: TextView = view.findViewById(R.id.tvNationalCode)
        val btnCallTeacher: MaterialButton = view.findViewById(R.id.btnCallTeacher)
        val btnViewProfile: MaterialButton = view.findViewById(R.id.btnViewProfile)
        val btnViewClasses: MaterialButton = view.findViewById(R.id.btnViewClasses)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): TeacherViewHolder {
        val view = LayoutInflater.from(parent.context)
            .inflate(R.layout.item_teacher_improved, parent, false)
        return TeacherViewHolder(view)
    }

    override fun onBindViewHolder(holder: TeacherViewHolder, position: Int) {
        val item = list[position]
        // FIX(null-data): نام/موبایل/کد ملی legacy ممکن است null باشند — فال‌بک امن در نمایش و
        // تله‌ی نهایی: یک رکورد ناقص نباید کل RecyclerView لیست مربیان را crash کند.
        try {
            holder.tvTeacherName.text = item.name ?: ""
            holder.tvTeacherMobile.text = holder.itemView.context.getString(R.string.common_mobile_row, item.mobile ?: "")
            holder.tvNationalCode.text = holder.itemView.context.getString(R.string.plist_national_row, item.national_code ?: "")

            if (item.is_suspended) {
                holder.tvTeacherStatus.text = holder.itemView.context.getString(R.string.tprof_suspended)
                holder.tvTeacherStatus.setTextColor(UiColors.resolve(holder.itemView.context, R.color.status_warning))
            } else {
                holder.tvTeacherStatus.text = holder.itemView.context.getString(R.string.tprof_active)
                holder.tvTeacherStatus.setTextColor(UiColors.resolve(holder.itemView.context, R.color.status_success))
            }

            holder.btnCallTeacher.setOnClickListener {
                if (!item.mobile.isNullOrBlank()) {
                    val intent = Intent(Intent.ACTION_DIAL, Uri.parse("tel:${item.mobile}"))
                    holder.itemView.context.startActivity(intent)
                } else {
                    Toast.makeText(holder.itemView.context, holder.itemView.context.getString(R.string.plist_no_phone), Toast.LENGTH_SHORT).show()
                }
            }

            holder.btnViewProfile.setOnClickListener {
                val intent = Intent(holder.itemView.context, TeacherProfileActivity::class.java)
                intent.putExtra("TEACHER_ID", item.id)
                holder.itemView.context.startActivity(intent)
            }

            holder.btnViewClasses.setOnClickListener {
                val intent = Intent(holder.itemView.context, TeacherProfileActivity::class.java)
                intent.putExtra("TEACHER_ID", item.id)
                holder.itemView.context.startActivity(intent)
            }

            holder.itemView.setOnClickListener {
                val intent = Intent(holder.itemView.context, TeacherProfileActivity::class.java)
                intent.putExtra("TEACHER_ID", item.id)
                holder.itemView.context.startActivity(intent)
            }
        } catch (e: Exception) {
            android.util.Log.e("ImprovedTeacherAdapter", "Error binding row ${item.id}", e)
        }
    }

    override fun getItemCount() = list.size
}
