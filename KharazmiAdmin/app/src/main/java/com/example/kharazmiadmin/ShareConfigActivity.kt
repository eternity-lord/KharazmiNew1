package com.example.kharazmiadmin

import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.Toast
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST

// مدل داده منطبق با سرور
data class ShareConfigData(
    val count_1: Long, val count_2: Long, val count_3: Long, val count_4: Long, val count_5: Long,
    val count_6: Long, val count_7: Long, val count_8: Long, val count_9: Long, val count_10: Long,
    val count_11: Long, val count_12: Long, val count_13: Long, val count_14: Long, val count_15: Long
)

// API
interface ShareApi {
    @GET("config/share")
    suspend fun getShares(): ShareConfigData

    @POST("config/share/update")
    suspend fun updateShares(@Body data: ShareConfigData): SimpleResponse
}

class ShareConfigActivity : BaseActivity() {

    // آرایه‌ای از EditText ها برای دسترسی راحت‌تر
    private val etList = ArrayList<EditText>()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_share_config)

        // پیدا کردن فیلدها به صورت هوشمند (از et1 تا et15)
        for (i in 1..15) {
            val id = resources.getIdentifier("et$i", "id", packageName)
            etList.add(findViewById(id))
        }

        findViewById<Button>(R.id.btnSaveShare).setOnClickListener {
            saveData()
        }

        loadData()
    }

    private fun loadData() {
        val retrofit = RetrofitClient.getInstance(this)
        val api = retrofit.create(ShareApi::class.java)

        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.

        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val data = api.getShares()
                withContext(Dispatchers.Main) {
                    // پر کردن فیلدها با مقادیر دریافتی از سرور
                    etList[0].setText(data.count_1.toString())
                    etList[1].setText(data.count_2.toString())
                    etList[2].setText(data.count_3.toString())
                    etList[3].setText(data.count_4.toString())
                    etList[4].setText(data.count_5.toString())
                    etList[5].setText(data.count_6.toString())
                    etList[6].setText(data.count_7.toString())
                    etList[7].setText(data.count_8.toString())
                    etList[8].setText(data.count_9.toString())
                    etList[9].setText(data.count_10.toString())
                    etList[10].setText(data.count_11.toString())
                    etList[11].setText(data.count_12.toString())
                    etList[12].setText(data.count_13.toString())
                    etList[13].setText(data.count_14.toString())
                    etList[14].setText(data.count_15.toString())
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@ShareConfigActivity, getString(R.string.shcfg_load_error), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun saveData() {
        // خواندن مقادیر از فیلدها (اگر خالی بود 0 در نظر میگیرد)
        val vals = etList.map { it.text.toString().toLongOrNull() ?: 0 }

        val data = ShareConfigData(
            vals[0], vals[1], vals[2], vals[3], vals[4],
            vals[5], vals[6], vals[7], vals[8], vals[9],
            vals[10], vals[11], vals[12], vals[13], vals[14]
        )

        val retrofit = RetrofitClient.getInstance(this)
        val api = retrofit.create(ShareApi::class.java)

        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.

        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val res = api.updateShares(data)
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@ShareConfigActivity, getString(R.string.common_ok_msg, res.message), Toast.LENGTH_LONG).show()
                    finish()
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@ShareConfigActivity, getString(R.string.shcfg_save_error), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }
}
