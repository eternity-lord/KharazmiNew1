package com.example.kharazmiadmin

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.ArrayAdapter
import android.widget.AutoCompleteTextView
import android.widget.Button
import android.widget.TextView
import android.widget.Toast
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.google.android.material.textfield.TextInputEditText
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST

// مدل‌ها
data class SmsRequest(val target_group: String, val message_text: String)
data class SmsResponse(val message: String, val count: Int)
data class SmsLogItem(val target_group: String, val message_text: String, val sent_count: Int, val date: String)

interface SmsApi {
    @POST("sms/send")
    suspend fun sendSms(@Body req: SmsRequest): SmsResponse

    @GET("sms/history")
    suspend fun getHistory(): List<SmsLogItem>
}

class SmsActivity : BaseActivity() {

    private lateinit var api: SmsApi
    private lateinit var rvHistory: RecyclerView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_sms)

        rvHistory = findViewById(R.id.rvSmsHistory)
        rvHistory.layoutManager = LinearLayoutManager(this)

        val tabLayout = findViewById<com.google.android.material.tabs.TabLayout>(R.id.tabLayoutSms)
        val llSend = findViewById<View>(R.id.llSendSmsContainer)
        val llHistory = findViewById<View>(R.id.llHistorySmsContainer)

        tabLayout.addOnTabSelectedListener(object : com.google.android.material.tabs.TabLayout.OnTabSelectedListener {
            override fun onTabSelected(tab: com.google.android.material.tabs.TabLayout.Tab?) {
                if (tab?.position == 0) {
                    llSend.visibility = View.VISIBLE
                    llHistory.visibility = View.GONE
                } else {
                    llSend.visibility = View.GONE
                    llHistory.visibility = View.VISIBLE
                }
            }
            override fun onTabUnselected(tab: com.google.android.material.tabs.TabLayout.Tab?) {}
            override fun onTabReselected(tab: com.google.android.material.tabs.TabLayout.Tab?) {}
        })

        // تنظیم منوی کشویی
        val targets = arrayOf("همه دانش‌آموزان", "همه معلمان", "بدهکاران")
        val adapter = ArrayAdapter(this, android.R.layout.simple_dropdown_item_1line, targets)
        val acTarget = findViewById<AutoCompleteTextView>(R.id.acTarget)
        acTarget.setAdapter(adapter)

        // اتصال سرور
        val retrofit = RetrofitClient.getInstance(this)
        api = retrofit.create(SmsApi::class.java)

        fetchHistory()

        findViewById<Button>(R.id.btnSendSms).setOnClickListener {
            val msg = findViewById<TextInputEditText>(R.id.etMessage).text.toString()
            if (msg.isNotEmpty()) {
                // تبدیل متن فارسی منو به کد انگلیسی برای سرور
                val targetCode = when (acTarget.text.toString()) {
                    "همه دانش‌آموزان" -> "all_students"
                    "همه معلمان" -> "all_teachers"
                    else -> "debtors"
                }
                sendSms(targetCode, msg)
            } else {
                Toast.makeText(this, getString(R.string.sms_write_msg), Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun sendSms(target: String, msg: String) {
        // FIX L9: ضد دابل‌کلیک (پیامک تکراری = هزینه) — در هر دو مسیر برمی‌گردد.
        findViewById<Button>(R.id.btnSendSms).isEnabled = false
        val req = SmsRequest(target, msg)
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val res = api.sendSms(req)
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@SmsActivity, getString(R.string.sms_sent, res.count), Toast.LENGTH_LONG).show()
                    findViewById<Button>(R.id.btnSendSms).isEnabled = true
                    findViewById<TextInputEditText>(R.id.etMessage).text = null
                    fetchHistory() // آپدیت لیست
                }
            } catch (e: Exception) {
                // Cancellation is lifecycle control, not a delivery failure.
                if (e is kotlinx.coroutines.CancellationException) throw e
                android.util.Log.e("SmsActivity", "sendSms failed", e)
                withContext(Dispatchers.Main) {
                    findViewById<Button>(R.id.btnSendSms).isEnabled = true
                    Toast.makeText(
                        this@SmsActivity,
                        "ارسال پیامک انجام نشد: ${e.message ?: "خطای سرور یا شبکه"}",
                        Toast.LENGTH_LONG
                    ).show()
                }
            }
        }
    }

    private fun fetchHistory() {
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val list = api.getHistory()
                withContext(Dispatchers.Main) {
                    rvHistory.adapter = SmsAdapter(list)
                }
            } catch (e: Exception) {
                // Cancellation is lifecycle control, not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e
                android.util.Log.e("SmsActivity", "fetchHistory failed", e)
                withContext(Dispatchers.Main) {
                    Toast.makeText(
                        this@SmsActivity,
                        "تاریخچه پیامک بارگذاری نشد: ${e.message ?: "خطای سرور یا شبکه"}",
                        Toast.LENGTH_LONG
                    ).show()
                }
            }
        }
    }
}

class SmsAdapter(private val list: List<SmsLogItem>) : RecyclerView.Adapter<SmsAdapter.VH>() {
    class VH(v: View) : RecyclerView.ViewHolder(v) {
        val target: TextView = v.findViewById(R.id.tvTarget)
        val msg: TextView = v.findViewById(R.id.tvMsg)
        val date: TextView = v.findViewById(R.id.tvDate)
        val count: TextView = v.findViewById(R.id.tvCount)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val v = LayoutInflater.from(parent.context).inflate(R.layout.item_sms, parent, false)
        return VH(v)
    }

    override fun onBindViewHolder(holder: VH, position: Int) {
        val item = list[position]
        // تبدیل کد به فارسی برای نمایش
        val targetFa = when (item.target_group) {
            "all_students" -> "همه دانش‌آموزان"
            "all_teachers" -> "همه معلمان"
            else -> "بدهکاران"
        }
        holder.target.text = holder.itemView.context.getString(R.string.sms_to_row, targetFa)
        holder.msg.text = item.message_text
        holder.date.text = item.date
        holder.count.text = holder.itemView.context.getString(R.string.sms_count_row, item.sent_count)
    }

    override fun getItemCount() = list.size
}
