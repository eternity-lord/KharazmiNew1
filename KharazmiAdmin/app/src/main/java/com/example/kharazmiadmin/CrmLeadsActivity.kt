package com.example.kharazmiadmin

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.*
import androidx.appcompat.app.AlertDialog
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.google.android.material.button.MaterialButton
import com.google.android.material.card.MaterialCardView
import com.google.android.material.textfield.TextInputEditText
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import retrofit2.HttpException
import retrofit2.http.*

// API Models for CRM
data class LeadCreateRequest(
    val name: String,
    val mobile: String,
    val interested_course: String,
    val source: String = "Web",
    val notes: String? = null,
    val next_follow_up: String? = null,
    val branch_id: Int? = null
)

data class LeadResponseModel(
    val id: Int,
    val name: String,
    val mobile: String,
    val interested_course: String,
    val source: String,
    val status: String,
    val notes: String? = null,
    val next_follow_up: String? = null,
    val created_at: String
)

data class LeadNoteRequest(
    val notes: String,
    val next_follow_up: String? = null,
    val status: String? = null
)

interface CrmNetworkApi {
    @POST("crm/leads/create")
    suspend fun createLead(@Body req: LeadCreateRequest): LeadResponseModel

    @GET("crm/leads/list")
    suspend fun getLeadsList(): List<LeadResponseModel>

    @POST("crm/leads/{id}/notes")
    suspend fun addNotes(@Path("id") id: Int, @Body req: LeadNoteRequest): SimpleResponse

    @POST("crm/leads/{id}/convert")
    suspend fun convertLead(@Path("id") id: Int): SimpleResponse
}

class CrmLeadsActivity : BaseActivity() {

    private lateinit var flipper: ViewFlipper
    private lateinit var rvLeads: RecyclerView
    private lateinit var etName: TextInputEditText
    private lateinit var etMobile: TextInputEditText
    private lateinit var etCourse: TextInputEditText
    private lateinit var btnSubmit: Button

    // Details Views
    private lateinit var tvDetailName: TextView
    private lateinit var tvDetailMobile: TextView
    private lateinit var tvDetailCourse: TextView
    private lateinit var tvDetailStatus: TextView
    private lateinit var etNotesInput: TextInputEditText
    private lateinit var etNextFollowUp: TextInputEditText
    private lateinit var btnSaveNotes: Button
    private lateinit var btnConvert: Button
    private lateinit var btnBack: Button

    private lateinit var api: CrmNetworkApi
    private var activeLeadId: Int = -1

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_crm_leads)

        initViews()
        setupApi()
        setupListeners()
        loadLeads()
    }

    private fun initViews() {
        flipper = findViewById(R.id.crmFlipper)
        rvLeads = findViewById(R.id.rvLeads)
        etName = findViewById(R.id.etLeadName)
        etMobile = findViewById(R.id.etLeadMobile)
        etCourse = findViewById(R.id.etLeadCourse)
        btnSubmit = findViewById(R.id.btnSubmitLead)

        tvDetailName = findViewById(R.id.tvLeadDetailName)
        tvDetailMobile = findViewById(R.id.tvLeadDetailMobile)
        tvDetailCourse = findViewById(R.id.tvLeadDetailCourse)
        tvDetailStatus = findViewById(R.id.tvLeadDetailStatus)
        etNotesInput = findViewById(R.id.etLeadNotesInput)
        etNextFollowUp = findViewById(R.id.etLeadNextFollowUp)
        btnSaveNotes = findViewById(R.id.btnSaveLeadNotes)
        btnConvert = findViewById(R.id.btnConvertLead)
        btnBack = findViewById(R.id.btnBackLeadsList)

        rvLeads.layoutManager = LinearLayoutManager(this)
    }

    private fun setupApi() {
        val retrofit = RetrofitClient.getInstance(this)
        api = retrofit.create(CrmNetworkApi::class.java)
    }

    private fun setupListeners() {
        btnSubmit.setOnClickListener {
            val name = etName.text.toString().trim()
            val mobile = etMobile.text.toString().trim()
            val course = etCourse.text.toString().trim()

            if (name.isEmpty() || mobile.isEmpty() || course.isEmpty()) {
                Toast.makeText(this, getString(R.string.crm_fill), Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }

            createLeadOnServer(name, mobile, course)
        }

        btnSaveNotes.setOnClickListener {
            val notes = etNotesInput.text.toString().trim()
            val followUp = etNextFollowUp.text.toString().trim()

            if (notes.isEmpty()) {
                Toast.makeText(this, getString(R.string.crm_note_empty), Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }

            saveNotesOnServer(notes, followUp)
        }

        btnConvert.setOnClickListener {
            AlertDialog.Builder(this)
                .setTitle(getString(R.string.crm_conv_title))
                .setMessage(getString(R.string.crm_conv_msg))
                .setPositiveButton(getString(R.string.crm_conv_yes)) { _, _ ->
                    convertLeadOnServer()
                }
                .setNegativeButton(getString(R.string.common_cancel), null)
                .show()
        }

        btnBack.setOnClickListener {
            flipper.displayedChild = 0 // Return to pipeline list
            loadLeads()
        }
    }

    private fun createLeadOnServer(name: String, mobile: String, course: String) {
        val branchId = getSharedPreferences("UserCreds", Context.MODE_PRIVATE)
            .getInt("USER_BRANCH_ID", 1)
        val req = LeadCreateRequest(
            name = name,
            mobile = mobile,
            interested_course = course,
            branch_id = branchId,
        )
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                api.createLead(req)
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@CrmLeadsActivity, getString(R.string.crm_lead_done), Toast.LENGTH_SHORT).show()
                    etName.text = null
                    etMobile.text = null
                    etCourse.text = null
                    loadLeads() // Reload
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    // FIX(crm): 4xx → detail کنترل‌شده‌ی سرور (مثلاً «شعبه انتخابی معتبر یا فعال نیست»)
                    val detail = serverErrorDetail(e)
                    val msg = if (detail != null) getString(R.string.crm_error_detail, detail) else getString(R.string.crm_lead_error)
                    Toast.makeText(this@CrmLeadsActivity, msg, Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    // FIX(crm): «detail» کنترل‌شده‌ی سرور از بدنه‌ی خطای 4xx؛ غیر-HTTP یا بدنه‌ی غیرJSON → null
    private fun serverErrorDetail(e: Exception): String? {
        val http = e as? HttpException ?: return null
        if (http.code() !in 400..499) return null
        return try {
            http.response()?.errorBody()?.string()?.let { body ->
                org.json.JSONObject(body).optString("detail").takeIf { it.isNotBlank() }
            }
        } catch (ignored: Exception) {
            null
        }
    }

    private fun loadLeads() {
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val list = api.getLeadsList()
                withContext(Dispatchers.Main) {
                    if (list.isEmpty()) {
                        Toast.makeText(this@CrmLeadsActivity, getString(R.string.crm_lead_empty), Toast.LENGTH_SHORT).show()
                    }
                    rvLeads.adapter = LeadsAdapter(list) { lead ->
                        showLeadDetails(lead)
                    }
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@CrmLeadsActivity, getString(R.string.crm_leads_error), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun showLeadDetails(lead: LeadResponseModel) {
        activeLeadId = lead.id
        flipper.displayedChild = 1 // Switch to details
        
        tvDetailName.text = getString(R.string.crm_det_name, lead.name)
        tvDetailMobile.text = getString(R.string.crm_det_mobile, lead.mobile)
        tvDetailCourse.text = getString(R.string.crm_det_course, lead.interested_course)
        tvDetailStatus.text = getString(R.string.crm_det_status, lead.status)
        
        etNotesInput.setText(lead.notes ?: "")
        etNextFollowUp.setText(lead.next_follow_up ?: "")
    }

    private fun saveNotesOnServer(notes: String, followUp: String) {
        val req = LeadNoteRequest(notes, followUp.ifEmpty { null }, "CONTACTED")
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                api.addNotes(activeLeadId, req)
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@CrmLeadsActivity, getString(R.string.crm_note_done), Toast.LENGTH_SHORT).show()
                    flipper.displayedChild = 0 // Go back
                    loadLeads()
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@CrmLeadsActivity, getString(R.string.crm_note_error), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun convertLeadOnServer() {
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val res = api.convertLead(activeLeadId)
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@CrmLeadsActivity, getString(R.string.common_ok_msg, res.message), Toast.LENGTH_LONG).show()
                    
                    // ابطال کش لیست دانش‌آموزان ادمین
                    CacheManager.clearByPrefix(this@CrmLeadsActivity, "person_list_STUDENT")
                    
                    flipper.displayedChild = 0
                    loadLeads()
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    // FIX(crm): 4xx → detail کنترل‌شده‌ی سرور (مثلاً «موبایل سرنخ خالی است…»)
                    val detail = serverErrorDetail(e)
                    val msg = if (detail != null) getString(R.string.crm_error_detail, detail) else getString(R.string.crm_conv_error)
                    Toast.makeText(this@CrmLeadsActivity, msg, Toast.LENGTH_LONG).show()
                }
            }
        }
    }
}

class LeadsAdapter(
    private val list: List<LeadResponseModel>,
    private val onClick: (LeadResponseModel) -> Unit
) : RecyclerView.Adapter<LeadsAdapter.VH>() {

    class VH(v: View) : RecyclerView.ViewHolder(v) {
        val name: TextView = v.findViewById(R.id.tvLeadName)
        val course: TextView = v.findViewById(R.id.tvLeadCourse)
        val followUp: TextView = v.findViewById(R.id.tvLeadFollowUp)
        val status: TextView = v.findViewById(R.id.tvLeadStatus)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val v = LayoutInflater.from(parent.context).inflate(R.layout.item_lead, parent, false)
        return VH(v)
    }

    override fun onBindViewHolder(holder: VH, position: Int) {
        val item = list[position]
        holder.name.text = holder.itemView.context.getString(R.string.common_person_row, item.name)
        holder.course.text = holder.itemView.context.getString(R.string.crm_row_course, item.interested_course)
        holder.followUp.text = holder.itemView.context.getString(R.string.crm_row_follow, item.next_follow_up ?: holder.itemView.context.getString(R.string.crm_unset))
        holder.status.text = item.status
        
        holder.itemView.setOnClickListener { onClick(item) }
    }

    override fun getItemCount() = list.size
}
