package com.example.kharazmiadmin

import android.os.Bundle
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog // FIX (audit-v2/blind-approve-2c): دیالوگ هشدار مبلغ
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class PendingClassDetailActivity : BaseActivity() {

    private var courseId: Int = -1
    private var teacherPrice: Long = 0
    private lateinit var rv: RecyclerView

    // استفاده از اینترفیس‌های عمومی
    private lateinit var invoiceApi: InvoiceApi
    private lateinit var adminApi: AdminClassApi

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_pending_class_detail)

        courseId = intent.getIntExtra("COURSE_ID", -1)
        teacherPrice = intent.getLongExtra("TEACHER_PRICE", 0)
        val instituteShare = intent.getLongExtra("INSTITUTE_SHARE", 0)
        val title = intent.getStringExtra("TITLE") ?: ""

        findViewById<TextView>(R.id.tvHeaderTitle).text = getString(R.string.pclsdet_header, title)
        // FIX (audit-v2/blind-approve-2b): نمایش مبلغ واقعی قبل از تأیید — قبلاً هاردکد «۰» بود.
        findViewById<TextView>(R.id.tvTeacherAsk).text = String.format("%,d", teacherPrice)
        findViewById<TextView>(R.id.tvInstShare).text = String.format("%,d", instituteShare)
        findViewById<TextView>(R.id.tvFinalCost).text = getString(R.string.common_toman_format, teacherPrice + instituteShare)
        rv = findViewById(R.id.rvStudentsPreview)
        rv.layoutManager = LinearLayoutManager(this)

        val retrofit = RetrofitClient.getInstance(this)
        invoiceApi = retrofit.create(InvoiceApi::class.java) // ✅ Fix: استفاده از فایل ApiInterfaces
        adminApi = retrofit.create(AdminClassApi::class.java)

        loadStudents()

        findViewById<View>(R.id.btnConfirmClass).setOnClickListener {
            approveClass()
        }
    }

    private fun loadStudents() {
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                // استفاده از متد مشترک getClassDetails
                val response = invoiceApi.getClassDetails(courseId)
                withContext(Dispatchers.Main) {
                    if (response.students.isEmpty()) {
                        Toast.makeText(this@PendingClassDetailActivity, getString(R.string.pclsdet_no_student), Toast.LENGTH_SHORT).show()
                    }
                    rv.adapter = PendingStudentAdapter(response.students)
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                // خطا هندل شود
            }
        }
    }

    private fun approveClass() {
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val res = adminApi.approveClass(courseId)
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@PendingClassDetailActivity, getString(R.string.common_ok_msg, res.message), Toast.LENGTH_LONG).show()
                    // FIX (audit-v2/blind-approve-2c): نرخ بالای سقف → دیالوگ هشدار؛ خروج بعد از تأیید کاربر.
                    if (!res.price_warning.isNullOrEmpty()) {
                        AlertDialog.Builder(this@PendingClassDetailActivity)
                            .setTitle(getString(R.string.pclsdet_warn_title))
                            .setMessage(res.price_warning)
                            .setPositiveButton(getString(R.string.pclsdet_understood)) { _, _ -> finish() }
                            .setOnCancelListener { finish() }
                            .show()
                    } else {
                        finish()
                    }
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@PendingClassDetailActivity, getString(R.string.pclsdet_op_error), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    inner class PendingStudentAdapter(private val list: List<StudentItem>) : RecyclerView.Adapter<PendingStudentAdapter.VH>() {
        inner class VH(v: View) : RecyclerView.ViewHolder(v) {
            val tvName: TextView = v.findViewById(android.R.id.text1)
        }
        override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
            val v = android.view.LayoutInflater.from(parent.context).inflate(android.R.layout.simple_list_item_1, parent, false)
            return VH(v)
        }
        override fun onBindViewHolder(holder: VH, position: Int) {
            holder.tvName.text = "${position + 1}. ${list[position].student_name}"
        }
        override fun getItemCount() = list.size
    }
}
