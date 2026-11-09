package com.example.kharazmiadmin

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.CheckBox
import android.widget.ProgressBar
import android.widget.TextView
import android.widget.Toast
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.google.android.material.button.MaterialButton
import com.google.android.material.card.MaterialCardView
import com.google.android.material.floatingactionbutton.ExtendedFloatingActionButton
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import retrofit2.HttpException

class DunningActivity : BaseActivity() {

    private lateinit var rvDrafts: RecyclerView
    private lateinit var tvEmpty: TextView
    private lateinit var progress: ProgressBar
    private lateinit var btnSelectAll: MaterialButton
    private lateinit var btnDeselectAll: MaterialButton
    private lateinit var btnRefresh: MaterialButton
    private lateinit var btnBack: MaterialButton
    private lateinit var fabSend: ExtendedFloatingActionButton
    private lateinit var tvTitle: TextView

    private lateinit var api: DunningApi
    private var drafts: List<DunningDraft> = emptyList()
    private val selectedIds = mutableSetOf<Int>()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_dunning)

        initViews()
        setupApi()
        setupListeners()
        loadDrafts()
    }

    private fun initViews() {
        rvDrafts = findViewById(R.id.rvDunningDrafts)
        tvEmpty = findViewById(R.id.tvDunningEmpty)
        progress = findViewById(R.id.progressDunning)
        btnSelectAll = findViewById(R.id.btnSelectAll)
        btnDeselectAll = findViewById(R.id.btnDeselectAll)
        btnRefresh = findViewById(R.id.btnDunningRefresh)
        btnBack = findViewById(R.id.btnDunningBack)
        fabSend = findViewById(R.id.fabSend)
        tvTitle = findViewById(R.id.tvDunningTitle)

        rvDrafts.layoutManager = LinearLayoutManager(this)
        tvTitle.text = getString(R.string.dunning_title)
    }

    private fun setupApi() {
        val retrofit = RetrofitClient.getInstance(this)
        api = retrofit.create(DunningApi::class.java)
    }

    private fun setupListeners() {
        btnSelectAll.setOnClickListener {
            selectedIds.clear()
            selectedIds.addAll(drafts.map { it.installmentId })
            rvDrafts.adapter?.notifyDataSetChanged()
            updateFabCount()
        }
        btnDeselectAll.setOnClickListener {
            selectedIds.clear()
            rvDrafts.adapter?.notifyDataSetChanged()
            updateFabCount()
        }
        btnRefresh.setOnClickListener { loadDrafts() }
        btnBack.setOnClickListener { finish() }

        fabSend.setOnClickListener {
            if (selectedIds.isEmpty()) {
                Toast.makeText(this, getString(R.string.dunning_no_selection), Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }
            sendSelected()
        }
    }

    private fun updateFabCount() {
        fabSend.text = if (selectedIds.isEmpty()) {
            getString(R.string.dunning_send_selected)
        } else {
            "${getString(R.string.dunning_send_selected)} (${selectedIds.size})"
        }
    }

    private fun setLoading(isLoading: Boolean) {
        progress.visibility = if (isLoading) View.VISIBLE else View.GONE
        fabSend.isEnabled = !isLoading
        btnSelectAll.isEnabled = !isLoading
        btnDeselectAll.isEnabled = !isLoading
        btnRefresh.isEnabled = !isLoading
    }

    private fun loadDrafts() {
        tvEmpty.text = getString(R.string.dunning_loading)
        tvEmpty.visibility = View.VISIBLE
        rvDrafts.visibility = View.GONE
        setLoading(true)

        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val list = api.getDrafts()
                withContext(Dispatchers.Main) {
                    setLoading(false)
                    drafts = list
                    selectedIds.clear()
                    updateFabCount()
                    if (list.isEmpty()) {
                        tvEmpty.text = getString(R.string.dunning_empty)
                        tvEmpty.visibility = View.VISIBLE
                        rvDrafts.visibility = View.GONE
                    } else {
                        tvEmpty.visibility = View.GONE
                        rvDrafts.visibility = View.VISIBLE
                        rvDrafts.adapter = DunningAdapter(list)
                    }
                }
            } catch (e: Exception) {
                if (e is kotlinx.coroutines.CancellationException) throw e
                withContext(Dispatchers.Main) {
                    setLoading(false)
                    val msg = when (e) {
                        is HttpException -> when (e.code()) {
                            403 -> "⛔ دسترسی فقط برای ادمین"
                            401 -> "توکن منقضی شده — دوباره وارد شوید"
                            else -> getString(R.string.dunning_error, "خطای سرور ${e.code()}")
                        }
                        else -> getString(R.string.dunning_error, e.message ?: "خطا در دریافت")
                    }
                    tvEmpty.text = msg
                    tvEmpty.visibility = View.VISIBLE
                    rvDrafts.visibility = View.GONE
                    Toast.makeText(this@DunningActivity, msg, Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    private fun sendSelected() {
        setLoading(true)
        tvEmpty.text = getString(R.string.dunning_sending)
        tvEmpty.visibility = View.VISIBLE

        val idsToSend = selectedIds.toList()
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val resp = api.sendBatch(DunningSendRequest(idsToSend))
                withContext(Dispatchers.Main) {
                    setLoading(false)
                    tvEmpty.visibility = View.GONE
                    val msg = if (resp.sentCount > 0) {
                        getString(R.string.dunning_sent_ok, resp.sentCount) + " — ${resp.message}"
                    } else {
                        resp.message
                    }
                    Toast.makeText(this@DunningActivity, msg, Toast.LENGTH_LONG).show()
                    // Refresh: sent items disappear
                    loadDrafts()
                }
            } catch (e: Exception) {
                if (e is kotlinx.coroutines.CancellationException) throw e
                withContext(Dispatchers.Main) {
                    setLoading(false)
                    tvEmpty.visibility = View.GONE
                    val msg = when (e) {
                        is HttpException -> {
                            val body = e.response()?.errorBody()?.string()
                            val detail = try {
                                org.json.JSONObject(body ?: "").optString("detail", e.message ?: "")
                            } catch (_: Exception) { e.message ?: "" }
                            when (e.code()) {
                                403 -> "⛔ دسترسی فقط برای ادمین"
                                401 -> "توکن منقضی شده — دوباره وارد شوید"
                                else -> getString(R.string.dunning_error, detail.ifEmpty { "خطای سرور ${e.code()}" })
                            }
                        }
                        else -> getString(R.string.dunning_error, e.message ?: "خطا در ارسال")
                    }
                    Toast.makeText(this@DunningActivity, msg, Toast.LENGTH_LONG).show()
                    tvEmpty.text = msg
                    tvEmpty.visibility = View.VISIBLE
                }
            }
        }
    }

    inner class DunningAdapter(private val items: List<DunningDraft>) :
        RecyclerView.Adapter<DunningAdapter.VH>() {

        inner class VH(view: View) : RecyclerView.ViewHolder(view) {
            val card: MaterialCardView = view.findViewById(R.id.cardDunning)
            val cbSelect: CheckBox = view.findViewById(R.id.cbSelect)
            val tvStudentName: TextView = view.findViewById(R.id.tvStudentName)
            val tvAmount: TextView = view.findViewById(R.id.tvAmount)
            val tvCategory: TextView = view.findViewById(R.id.tvCategory)
            val tvDueDate: TextView = view.findViewById(R.id.tvDueDate)
            val tvParentMobile: TextView = view.findViewById(R.id.tvParentMobile)
            val tvSmsPreview: TextView = view.findViewById(R.id.tvSmsPreview)
        }

        override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
            val v = LayoutInflater.from(parent.context).inflate(R.layout.item_dunning_draft, parent, false)
            return VH(v)
        }

        override fun getItemCount(): Int = items.size

        override fun onBindViewHolder(holder: VH, position: Int) {
            val item = items[position]
            holder.tvStudentName.text = item.studentName
            holder.tvAmount.text = formatAmount(item.amount)
            holder.tvDueDate.text = "سررسید: ${item.dueDate}"
            holder.tvParentMobile.text = "📱 ${item.parentMobile}"
            holder.tvSmsPreview.text = item.suggestedMessage

            // Category badge & colors
            val (label, bgColor, strokeColor) = when (item.category) {
                "upcoming" -> Triple(
                    getString(R.string.dunning_filter_upcoming),
                    UiColors.resolve(holder.itemView.context, R.color.status_info_deep),
                    UiColors.resolve(holder.itemView.context, R.color.status_info)
                )
                "overdue" -> Triple(
                    getString(R.string.dunning_filter_overdue),
                    UiColors.resolve(holder.itemView.context, R.color.status_warning_deep),
                    UiColors.resolve(holder.itemView.context, R.color.status_warning)
                )
                "critical" -> Triple(
                    getString(R.string.dunning_filter_critical),
                    UiColors.resolve(holder.itemView.context, R.color.ds_danger_deep),
                    UiColors.resolve(holder.itemView.context, R.color.status_danger)
                )
                else -> Triple(
                    item.category,
                    UiColors.resolve(holder.itemView.context, R.color.status_neutral_deep),
                    UiColors.resolve(holder.itemView.context, R.color.text_secondary)
                )
            }
            // compute days string for overlay? preview already includes, but add status line
            val statusText = when (item.category) {
                "upcoming" -> "🔵 $label"
                "overdue" -> "⚠️ $label"
                "critical" -> "🔴 $label"
                else -> label
            }
            holder.tvCategory.text = statusText
            holder.tvCategory.setBackgroundColor(bgColor)
            holder.tvCategory.setTextColor(UiColors.resolve(holder.itemView.context, R.color.white))
            holder.card.strokeColor = strokeColor

            // Checkbox state - avoid triggering listener on recycle
            holder.cbSelect.setOnCheckedChangeListener(null)
            holder.cbSelect.isChecked = selectedIds.contains(item.installmentId)
            holder.cbSelect.setOnCheckedChangeListener { _, isChecked ->
                if (isChecked) selectedIds.add(item.installmentId) else selectedIds.remove(item.installmentId)
                updateFabCount()
            }
            // Card click toggles selection
            holder.card.setOnClickListener {
                holder.cbSelect.isChecked = !holder.cbSelect.isChecked
            }
        }

        private fun formatAmount(amount: Long): String {
            return try {
                String.format("%,d تومان", amount)
            } catch (_: Exception) {
                "$amount تومان"
            }
        }
    }
}
