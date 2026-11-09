package com.example.kharazmiadmin

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.text.Editable
import android.text.TextWatcher
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.ImageButton
import android.widget.TextView
import android.widget.Toast
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.google.android.material.textfield.TextInputEditText
import kotlinx.coroutines.*
import retrofit2.http.GET
import retrofit2.http.Query

interface ParentContactsApi {
    @GET("admin/parent_contacts")
    suspend fun getParentContacts(
        @Query("class_id") classId: Int?,
        @Query("search") search: String?
    ): List<ParentContactItem>
}

class ParentContactsActivity : BaseActivity() {

    private lateinit var rv: RecyclerView
    private lateinit var etSearch: TextInputEditText
    private lateinit var api: ParentContactsApi
    private var searchJob: Job? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_parent_contacts)

        rv = findViewById(R.id.rvContacts)
        etSearch = findViewById(R.id.etSearch)
        rv.layoutManager = LinearLayoutManager(this)

        val swipeRefreshLayout = findViewById<androidx.swiperefreshlayout.widget.SwipeRefreshLayout>(R.id.swipeRefreshLayout)
        swipeRefreshLayout.setOnRefreshListener {
            val query = etSearch.text.toString().trim()
            val cacheKey = "parent_contacts_" + query
            CacheManager.clear(this, cacheKey)
            fetchData(query)
            swipeRefreshLayout.isRefreshing = false
        }

        val retrofit = RetrofitClient.getInstance(this)
        api = retrofit.create(ParentContactsApi::class.java)

        // دریافت لیست اولیه دفترچه تلفن
        fetchData("")

        // جستجوی زنده
        etSearch.addTextChangedListener(object : TextWatcher {
            override fun afterTextChanged(s: Editable?) {
                searchJob?.cancel()
                // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
                searchJob = lifecycleScope.launch(Dispatchers.Main) {
                    delay(500) // تاخیر ۵۰۰ میلی‌ثانیه‌ای برای تایپ
                    fetchData(s.toString())
                }
            }
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {}
        })
    }

    private fun fetchData(query: String) {
        val cacheKey = "parent_contacts_" + query
        val type = object : com.google.gson.reflect.TypeToken<List<ParentContactItem>>() {}.type

        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.

        lifecycleScope.launch(Dispatchers.Main) {
            CachedApiCall.execute(
                context = this@ParentContactsActivity,
                cacheKey = cacheKey,
                type = type,
                networkCall = { api.getParentContacts(null, query.ifEmpty { null }) },
                onSuccess = { list, isOffline, timestamp ->
                    if (list.isEmpty() && query.isNotEmpty()) {
                        Toast.makeText(this@ParentContactsActivity, getString(R.string.pcon_empty), Toast.LENGTH_SHORT).show()
                    }
                    rv.adapter = ParentContactsAdapter(list)
                    if (isOffline) {
                        CachedApiCall.showOfflineBanner(this@ParentContactsActivity, timestamp)
                    } else {
                        CachedApiCall.hideOfflineBanner(this@ParentContactsActivity)
                    }
                },
                onFailure = {
                    Toast.makeText(this@ParentContactsActivity, getString(R.string.common_offline_empty), Toast.LENGTH_LONG).show()
                }
            )
        }
    }

    // آداپتور لیست شماره تماس‌ها
    inner class ParentContactsAdapter(private val list: List<ParentContactItem>) : RecyclerView.Adapter<ParentContactsAdapter.VH>() {

        inner class VH(v: View) : RecyclerView.ViewHolder(v) {
            val tvStudentName: TextView = v.findViewById(R.id.tvStudentName)
            val tvClasses: TextView = v.findViewById(R.id.tvClasses)
            val tvParentPhone: TextView = v.findViewById(R.id.tvParentPhone)
            val tvStudentPhone: TextView = v.findViewById(R.id.tvStudentPhone)
            val btnCallParent: ImageButton = v.findViewById(R.id.btnCallParent)
            val btnSmsParent: ImageButton = v.findViewById(R.id.btnSmsParent)
        }

        override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
            val v = LayoutInflater.from(parent.context).inflate(R.layout.item_parent_contact, parent, false)
            return VH(v)
        }

        override fun onBindViewHolder(holder: VH, position: Int) {
            val item = list[position]
            holder.tvStudentName.text = item.student_name
            holder.tvParentPhone.text = getString(R.string.pcon_par_phone, item.parent_mobile.ifEmpty { getString(R.string.pcon_unset) })
            holder.tvStudentPhone.text = getString(R.string.pcon_st_phone, item.student_mobile.ifEmpty { getString(R.string.pcon_unset) })
            
            val classesText = item.classes.joinToString("، ")
            holder.tvClasses.text = getString(R.string.pcon_classes, classesText.ifEmpty { getString(R.string.pcon_unenrolled) })

            // دکمه تماس مستقیم با والدین
            holder.btnCallParent.setOnClickListener {
                val phone = item.parent_mobile
                if (phone.isNotEmpty()) {
                    val intent = Intent(Intent.ACTION_DIAL, Uri.parse("tel:$phone"))
                    startActivity(intent)
                } else {
                    Toast.makeText(this@ParentContactsActivity, getString(R.string.pcon_no_phone), Toast.LENGTH_SHORT).show()
                }
            }

            // دکمه ارسال پیامک مستقیم به والدین
            holder.btnSmsParent.setOnClickListener {
                val phone = item.parent_mobile
                if (phone.isNotEmpty()) {
                    val intent = Intent(Intent.ACTION_SENDTO, Uri.parse("smsto:$phone"))
                    startActivity(intent)
                } else {
                    Toast.makeText(this@ParentContactsActivity, getString(R.string.pcon_no_phone), Toast.LENGTH_SHORT).show()
                }
            }
            
            // کلیک روی ردیف برای باز کردن پروفایل دانش‌آموز
            holder.itemView.setOnClickListener {
                val intent = Intent(this@ParentContactsActivity, StudentProfileActivity::class.java)
                intent.putExtra("STUDENT_ID", item.student_id)
                startActivity(intent)
            }
        }

        override fun getItemCount() = list.size
    }
}
