package com.example.kharazmiadmin

import android.content.Context
import android.os.Bundle
import android.text.Editable
import android.text.TextWatcher
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.google.android.material.button.MaterialButton
import com.google.android.material.textfield.TextInputEditText
import kotlinx.coroutines.*
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Path
import retrofit2.http.Query

// models
data class TeacherCredentialsResponse(
    val id: Int,
    // FIX(null-data): سرور برای رکورد legacy بدون موبایل/کد ملی/نام (قبل از فیکس) null می‌داد —
    // null‌پذیر تا صفحه‌ی پروفایل/مشخصات مربی با یک رکورد ناقص نشکند (fallback در نمایش).
    val name: String? = null,
    val national_code: String? = null,
    val mobile: String? = null,
    val teacher_code: Int?,
    val password: String,
    val card_number: String?
)

data class TeacherCredentialsUpdateRequest(
    val mobile: String,
    val card_number: String?
)

data class ResetPasswordResponse(
    val message: String,
    val new_password: String
)

interface TeacherCredentialsApi {
    @GET("admin/teachers/search")
    suspend fun searchTeachers(@Query("query") q: String?): List<PersonListItem>

    @GET("admin/teachers/{id}/credentials")
    suspend fun getCredentials(@Path("id") id: Int): TeacherCredentialsResponse

    @POST("admin/teachers/{id}/credentials/reset_password")
    suspend fun resetPassword(@Path("id") id: Int): ResetPasswordResponse

    @PUT("admin/teachers/{id}/credentials")
    suspend fun updateCredentials(@Path("id") id: Int, @Body req: TeacherCredentialsUpdateRequest): SimpleResponse
}

class TeacherCredentialsActivity : BaseActivity() {

    private lateinit var etSearch: TextInputEditText
    private lateinit var rvResults: RecyclerView
    private lateinit var llContainer: View
    private lateinit var tvName: TextView
    private lateinit var tvCode: TextView
    private lateinit var etMobile: TextInputEditText
    private lateinit var etCardNumber: TextInputEditText
    private lateinit var tvCurrentPassword: TextView
    private lateinit var btnSave: MaterialButton
    private lateinit var btnReset: MaterialButton

    private lateinit var api: TeacherCredentialsApi
    private var searchJob: Job? = null
    private var selectedTeacherId: Int = -1

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_teacher_credentials)

        // Verify only admin can access this page
        val credsPrefs = getSharedPreferences("UserCreds", Context.MODE_PRIVATE)
        val subRole = credsPrefs.getString("USER_SUB_ROLE", "admin") ?: "admin"
        if (subRole != "admin") {
            Toast.makeText(this, getString(R.string.tcred_no_access), Toast.LENGTH_SHORT).show()
            finish()
            return
        }

        initViews()
        setupApi()
        setupSearch()
        setupButtons()
    }

    private fun initViews() {
        etSearch = findViewById(R.id.etSearchTeacher)
        rvResults = findViewById(R.id.rvTeacherResults)
        llContainer = findViewById(R.id.llCredentialsContainer)
        tvName = findViewById(R.id.tvTeacherName)
        tvCode = findViewById(R.id.tvTeacherCode)
        etMobile = findViewById(R.id.etTeacherMobile)
        etCardNumber = findViewById(R.id.etTeacherCardNumber)
        tvCurrentPassword = findViewById(R.id.tvCurrentPassword)
        btnSave = findViewById(R.id.btnSaveCredentials)
        btnReset = findViewById(R.id.btnResetPassword)

        rvResults.layoutManager = LinearLayoutManager(this)
    }

    private fun setupApi() {
        val retrofit = RetrofitClient.getInstance(this)
        api = retrofit.create(TeacherCredentialsApi::class.java)
    }

    private fun setupSearch() {
        etSearch.addTextChangedListener(object : TextWatcher {
            override fun afterTextChanged(s: Editable?) {
                searchJob?.cancel()
                if (s.isNullOrEmpty()) {
                    rvResults.visibility = View.GONE
                    return
                }

                // FIX: Bug 19 - cancel screen work when this Activity is destroyed.

                searchJob = lifecycleScope.launch(Dispatchers.IO) {
                    delay(500)
                    try {
                        val results = api.searchTeachers(s.toString())
                        withContext(Dispatchers.Main) {
                            if (results.isNotEmpty()) {
                                rvResults.visibility = View.VISIBLE
                                rvResults.adapter = CredentialsSearchAdapter(results) { item ->
                                    onTeacherSelected(item.id)
                                }
                            } else {
                                rvResults.visibility = View.GONE
                            }
                        }
                    } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                        android.util.Log.e("TeacherCredentialsActivity", "afterTextChanged failed", e)
                    }
                }
            }
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {}
        })
    }

    private fun onTeacherSelected(teacherId: Int) {
        selectedTeacherId = teacherId
        rvResults.visibility = View.GONE
        etSearch.setText("")
        loadTeacherCredentials()
    }

    private fun loadTeacherCredentials() {
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val creds = api.getCredentials(selectedTeacherId)
                withContext(Dispatchers.Main) {
                    llContainer.visibility = View.VISIBLE
                    // FIX(null-data): فیلدهای ناقص نباید «null» نشان دهند یا به ویو null برسد.
                    tvName.text = creds.name ?: getString(R.string.common_person_unknown)
                    tvCode.text = getString(R.string.tcred_code_row, creds.teacher_code ?: getString(R.string.tcred_unset))
                    etMobile.setText(creds.mobile ?: "")
                    etCardNumber.setText(creds.card_number ?: "")
                    tvCurrentPassword.text = creds.password
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@TeacherCredentialsActivity, getString(R.string.tcred_load_error), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun setupButtons() {
        btnSave.setOnClickListener {
            val mobile = etMobile.text.toString().trim()
            val card = etCardNumber.text.toString().trim()

            if (mobile.isEmpty()) {
                Toast.makeText(this, getString(R.string.tcred_mobile_empty), Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }

            AlertDialog.Builder(this)
                .setTitle(getString(R.string.tcred_confirm_title))
                .setMessage(getString(R.string.tcred_confirm_msg))
                .setPositiveButton(getString(R.string.common_yes)) { _, _ ->
                    saveCredentials(mobile, card)
                }
                .setNegativeButton(getString(R.string.common_cancel), null)
                .show()
        }

        btnReset.setOnClickListener {
            AlertDialog.Builder(this)
                .setTitle(getString(R.string.tcred_pwd_title))
                .setMessage(getString(R.string.tcred_pwd_msg))
                .setPositiveButton(getString(R.string.tcred_pwd_yes)) { _, _ ->
                    resetPassword()
                }
                .setNegativeButton(getString(R.string.common_cancel), null)
                .show()
        }
    }

    private fun saveCredentials(mobile: String, card: String) {
        val req = TeacherCredentialsUpdateRequest(mobile, card.ifEmpty { null })
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val res = api.updateCredentials(selectedTeacherId, req)
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@TeacherCredentialsActivity, getString(R.string.common_ok_msg, res.message), Toast.LENGTH_LONG).show()
                    loadTeacherCredentials() // Reload
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@TeacherCredentialsActivity, getString(R.string.tcred_save_error), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun resetPassword() {
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val res = api.resetPassword(selectedTeacherId)
                withContext(Dispatchers.Main) {
                    // Show confirmation dialog with new password
                    AlertDialog.Builder(this@TeacherCredentialsActivity)
                        .setTitle(getString(R.string.tcred_pwd_ok_title))
                        .setMessage(getString(R.string.tcred_pwd_ok_msg, res.new_password))
                        .setPositiveButton(getString(R.string.common_understood), null)
                        .setCancelable(false)
                        .show()
                        
                    loadTeacherCredentials() // Reload
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@TeacherCredentialsActivity, getString(R.string.tcred_pwd_error), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }
}

class CredentialsSearchAdapter(
    private val list: List<PersonListItem>,
    private val onClick: (PersonListItem) -> Unit
) : RecyclerView.Adapter<CredentialsSearchAdapter.VH>() {

    class VH(v: View) : RecyclerView.ViewHolder(v) {
        val title: TextView = v.findViewById(android.R.id.text1)
        val subtitle: TextView = v.findViewById(android.R.id.text2)
        init {
            subtitle.textSize = 12f
            subtitle.setTextColor(UiColors.resolve(v.context, R.color.text_secondary))
        }
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val v = LayoutInflater.from(parent.context).inflate(android.R.layout.simple_list_item_2, parent, false)
        return VH(v)
    }

    override fun onBindViewHolder(holder: VH, position: Int) {
        val item = list[position]
        // FIX(null-data): رکورد ناقص (نام/کد ملی/موبایل null) نباید «null» در ردیف جستجو نشان دهد.
        val ctx = holder.itemView.context
        holder.title.text = ctx.getString(
            R.string.common_person_row,
            item.name ?: ctx.getString(R.string.common_person_unknown)
        )
        holder.subtitle.text = ctx.getString(R.string.tcred_sub_row, item.national_code ?: "", item.mobile ?: "")
        holder.itemView.setOnClickListener { onClick(item) }
    }

    override fun getItemCount() = list.size
}
