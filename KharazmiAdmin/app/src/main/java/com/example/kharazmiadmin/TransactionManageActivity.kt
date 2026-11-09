package com.example.kharazmiadmin

import android.content.Intent
import android.content.Context
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.EditText
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.google.android.material.button.MaterialButton
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.PUT
import retrofit2.http.Path
import retrofit2.http.Query

// 1. تعریف API داخلی همین صفحه
interface TransactionApi {
    @GET("admin/transactions/list")
    suspend fun getTransactions(@Query("search") search: String?): List<TransactionFullItem>

    @DELETE("admin/transactions/{id}")
    suspend fun deleteTransaction(@Path("id") id: Int): SimpleResponse

    @PUT("admin/transactions/{id}")
    suspend fun updateTransaction(@Path("id") id: Int, @Body data: TransactionUpdateData): SimpleResponse
}

class TransactionManageActivity : BaseActivity() {

    private lateinit var rv: RecyclerView
    private lateinit var api: TransactionApi
    private var currentList: List<TransactionFullItem> = emptyList()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_transaction_manage)

        // تغییر تایتل تولبار
        findViewById<TextView>(R.id.tvHeaderTitle)?.text = getString(R.string.txn_title)

        // مخفی کردن بخش فیلتر گزارش (چون برای این صفحه نیاز نیست)
        findViewById<View>(R.id.cardReportFilter)?.visibility = View.GONE

        rv = findViewById(R.id.rvReport)
        rv.layoutManager = LinearLayoutManager(this)

        val retrofit = RetrofitClient.getInstance(this)
        api = retrofit.create(TransactionApi::class.java)

        // دکمه خروجی Excel تراکنش‌ها
        findViewById<MaterialButton>(R.id.btnExportExcel).setOnClickListener {
            ReportExporter.exportToExcel(
                context = this,
                endpointUrl = "admin/transactions/list/excel",
                fileName = "transactions_report.xlsx",
                onStart = {
                    Toast.makeText(this, getString(R.string.txn_excel_start), Toast.LENGTH_SHORT).show()
                },
                onComplete = {
                    Toast.makeText(this, getString(R.string.txn_excel_done), Toast.LENGTH_SHORT).show()
                },
                onError = { errorMsg ->
                    Toast.makeText(this, getString(R.string.txn_excel_error, errorMsg), Toast.LENGTH_LONG).show()
                }
            )
        }

        // دکمه چاپ PDF تراکنش‌ها
        findViewById<MaterialButton>(R.id.btnExportPdf).setOnClickListener {
            if (currentList.isEmpty()) {
                Toast.makeText(this, getString(R.string.txn_print_empty), Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }

            val headers = listOf(getString(R.string.common_id), getString(R.string.classes_students), getString(R.string.txn_th_class), getString(R.string.txn_th_amount), getString(R.string.txn_th_date), getString(R.string.txn_th_desc))
            val rows = currentList.map { item ->
                listOf(
                    item.id.toString(),
                    item.student_name,
                    item.course_name,
                    String.format("%,d", item.amount),
                    item.date,
                    item.description ?: "---"
                )
            }

            ReportExporter.printPdfReport(
                context = this,
                title = getString(R.string.txn_report_title),
                headers = headers,
                rows = rows
            )
        }

        loadData(null)
    }

    private fun loadData(query: String?) {
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val list = api.getTransactions(query)
                currentList = list
                
                // محاسبه مجموع مبالغ تراکنش‌ها
                var totalSum: Long = 0
                list.forEach { totalSum += it.amount }

                withContext(Dispatchers.Main) {
                    rv.adapter = TransManageAdapter(list)
                    findViewById<TextView>(R.id.tvTotalSum)?.text = getString(R.string.common_toman_format, totalSum)
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@TransactionManageActivity, getString(R.string.common_list_error), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    // آداپتور داخلی
    inner class TransManageAdapter(private val list: List<TransactionFullItem>) : RecyclerView.Adapter<TransManageAdapter.VH>() {

        inner class VH(v: View) : RecyclerView.ViewHolder(v) {
            val tvName: TextView = v.findViewById(R.id.tvStudentName)
            val tvCourse: TextView = v.findViewById(R.id.tvCourseName)
            val tvAmount: TextView = v.findViewById(R.id.tvAmount)
            val tvDate: TextView = v.findViewById(R.id.tvDate)

            val btnDelete: MaterialButton = v.findViewById(R.id.btnDelete)
            val btnEdit: MaterialButton = v.findViewById(R.id.btnEdit)
            val btnPrint: MaterialButton = v.findViewById(R.id.btnPrint)
        }

        override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
            val v = LayoutInflater.from(parent.context).inflate(R.layout.item_transaction_admin, parent, false)
            return VH(v)
        }

        override fun onBindViewHolder(holder: VH, position: Int) {
            val item = list[position]
            val remittanceStr = if (item.remittance_number != null) getString(R.string.txn_remit_row, item.remittance_number) else ""
            holder.tvName.text = "${item.student_name}$remittanceStr"
            holder.tvCourse.text = getString(R.string.txn_course_row, item.course_name, item.description ?: "")
            holder.tvAmount.text = getString(R.string.txn_amount_row, String.format("%,d", item.amount))
            holder.tvDate.text = item.date

            val credsPrefs = getSharedPreferences("UserCreds", Context.MODE_PRIVATE)
            val subRole = credsPrefs.getString("USER_SUB_ROLE", "admin") ?: "admin"
            if (subRole == "secretary") {
                holder.btnDelete.visibility = View.GONE
                holder.btnEdit.visibility = View.GONE
            }

            // 1. حذف
            holder.btnDelete.setOnClickListener {
                AlertDialog.Builder(this@TransactionManageActivity)
                    .setTitle(getString(R.string.txn_del_title))
                    .setMessage(getString(R.string.txn_del_msg))
                    .setPositiveButton(getString(R.string.action_delete)) { _, _ -> deleteItem(item.id) }
                    .setNegativeButton(getString(R.string.common_cancel), null)
                    .show()
            }

            // 2. ویرایش
            holder.btnEdit.setOnClickListener {
                showEditDialog(item)
            }

            // 3. چاپ مجدد
            holder.btnPrint.setOnClickListener {
                // FIX H16: فقط شناسه پاس داده می‌شود؛ InvoiceActivity جزئیات را تازه از سرور می‌گیرد (رفع TOCTOU).
                val intent = Intent(this@TransactionManageActivity, InvoiceActivity::class.java)
                intent.putExtra("MODE", "REPRINT")
                intent.putExtra("RECEIPT_ID", item.id.toString())
                startActivity(intent)
            }
        }

        override fun getItemCount(): Int {
            return list.size
        }
    }

    private fun deleteItem(id: Int) {
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val res = api.deleteTransaction(id)
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@TransactionManageActivity, getString(R.string.common_ok_msg, res.message), Toast.LENGTH_SHORT).show()
                    loadData(null) // رفرش لیست
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) { Toast.makeText(this@TransactionManageActivity, getString(R.string.txn_del_error), Toast.LENGTH_SHORT).show() }
            }
        }
    }

    private fun showEditDialog(item: TransactionFullItem) {
        val view = LayoutInflater.from(this).inflate(R.layout.dialog_ip_input, null)
        val etInput = view.findViewById<EditText>(R.id.etIpInput)
        etInput.hint = getString(R.string.txn_amount_hint)
        etInput.inputType = android.text.InputType.TYPE_CLASS_NUMBER
        etInput.setText(item.amount.toString())

        AlertDialog.Builder(this)
            .setTitle(getString(R.string.txn_edit_title))
            .setView(view)
            .setPositiveButton(getString(R.string.action_save)) { _, _ ->
                val newAmount = etInput.text.toString().toLongOrNull()
                if (newAmount != null) {
                    updateItem(item.id, item.student_name, item.course_name, newAmount, item.description ?: "", item.date)
                }
            }
            .show()
    }

    private fun updateItem(id: Int, studentName: String, courseName: String, amount: Long, desc: String, date: String) {
        val data = TransactionUpdateData(amount, desc, date)
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                api.updateTransaction(id, data)
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@TransactionManageActivity, getString(R.string.txn_edit_done), Toast.LENGTH_SHORT).show()
                    
                    // به صورت خودکار فیش چاپی جدید با کلمه "اصلاح شده" صادر می‌گردد
                    // FIX H16: فقط شناسه (+ مهر اصلاح)؛ مقادیر تازه از سرور خوانده می‌شوند (به‌جای اکوی PUT).
                    val intent = Intent(this@TransactionManageActivity, InvoiceActivity::class.java).apply {
                        putExtra("MODE", "REPRINT")
                        putExtra("RECEIPT_ID", id.toString())
                        putExtra("IS_MODIFIED", true)
                    }
                    startActivity(intent)
                    loadData(null)
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) { Toast.makeText(this@TransactionManageActivity, getString(R.string.txn_edit_error), Toast.LENGTH_SHORT).show() }
            }
        }
    }
}
