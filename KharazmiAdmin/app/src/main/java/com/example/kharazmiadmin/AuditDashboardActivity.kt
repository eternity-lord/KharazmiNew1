package com.example.kharazmiadmin

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import android.widget.Toast
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.google.android.material.button.MaterialButton
import com.google.android.material.card.MaterialCardView
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import retrofit2.HttpException

class AuditDashboardActivity : BaseActivity() {

    private lateinit var rvAlerts: RecyclerView
    private lateinit var tvEmpty: TextView
    private lateinit var tvTitle: TextView
    private lateinit var btnRefresh: MaterialButton
    private lateinit var btnBack: MaterialButton

    private lateinit var api: AuditApi
    private var alerts: List<AuditAlert> = emptyList()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_audit_dashboard)

        initViews()
        setupApi()
        setupListeners()
        loadAlerts()
    }

    private fun initViews() {
        rvAlerts = findViewById(R.id.rvAuditAlerts)
        tvEmpty = findViewById(R.id.tvAuditEmpty)
        tvTitle = findViewById(R.id.tvAuditTitle)
        btnRefresh = findViewById(R.id.btnAuditRefresh)
        btnBack = findViewById(R.id.btnAuditBack)

        rvAlerts.layoutManager = LinearLayoutManager(this)
        tvTitle.text = "Audit Radar — رادار تقلب"
    }

    private fun setupApi() {
        val retrofit = RetrofitClient.getInstance(this)
        api = retrofit.create(AuditApi::class.java)
    }

    private fun setupListeners() {
        btnRefresh.setOnClickListener {
            loadAlerts()
        }
        btnBack.setOnClickListener {
            finish()
        }
    }

    private fun loadAlerts() {
        tvEmpty.text = "در حال بارگذاری..."
        tvEmpty.visibility = View.VISIBLE
        rvAlerts.visibility = View.GONE

        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val list = api.getSuspiciousPatterns()
                withContext(Dispatchers.Main) {
                    alerts = list
                    if (list.isEmpty()) {
                        tvEmpty.text = "هیچ الگوی مشکوکی یافت نشد ✓"
                        tvEmpty.visibility = View.VISIBLE
                        rvAlerts.visibility = View.GONE
                    } else {
                        tvEmpty.visibility = View.GONE
                        rvAlerts.visibility = View.VISIBLE
                        rvAlerts.adapter = AuditAlertAdapter(list)
                    }
                }
            } catch (e: Exception) {
                if (e is kotlinx.coroutines.CancellationException) throw e
                withContext(Dispatchers.Main) {
                    val msg = when (e) {
                        is HttpException -> when (e.code()) {
                            403 -> "⛔ دسترسی فقط برای ادمین"
                            401 -> "توکن منقضی شده — دوباره وارد شوید"
                            else -> "خطای سرور: ${e.code()}"
                        }
                        else -> e.message ?: "خطا در دریافت داده"
                    }
                    tvEmpty.text = msg
                    tvEmpty.visibility = View.VISIBLE
                    rvAlerts.visibility = View.GONE
                    Toast.makeText(this@AuditDashboardActivity, msg, Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    inner class AuditAlertAdapter(private val items: List<AuditAlert>) :
        RecyclerView.Adapter<AuditAlertAdapter.VH>() {

        inner class VH(view: View) : RecyclerView.ViewHolder(view) {
            val card: MaterialCardView = view.findViewById(R.id.cardAlert)
            val tvType: TextView = view.findViewById(R.id.tvAlertType)
            val tvSeverity: TextView = view.findViewById(R.id.tvAlertSeverity)
            val tvTitle: TextView = view.findViewById(R.id.tvAlertTitle)
            val tvDesc: TextView = view.findViewById(R.id.tvAlertDesc)
            val tvEntity: TextView = view.findViewById(R.id.tvAlertEntity)
            val tvDetected: TextView = view.findViewById(R.id.tvAlertDetected)
        }

        override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
            val v = LayoutInflater.from(parent.context)
                .inflate(R.layout.item_audit_alert, parent, false)
            return VH(v)
        }

        override fun getItemCount(): Int = items.size

        override fun onBindViewHolder(holder: VH, position: Int) {
            val item = items[position]
            holder.tvType.text = item.type
            holder.tvSeverity.text = item.severity.uppercase()
            holder.tvTitle.text = item.title
            holder.tvDesc.text = item.description
            holder.tvEntity.text = "موجودیت: ${item.entityName} (#${item.entityId})"
            holder.tvDetected.text = "شناسایی: ${item.detectedAt}"

            // Color-code based on severity
            val context = holder.itemView.context
            val (bgColor, strokeColor, severityColor) = when (item.severity.lowercase()) {
                "high" -> Triple(
                    UiColors.resolve(context, R.color.ds_danger_container),
                    UiColors.resolve(context, R.color.ds_danger),
                    UiColors.resolve(context, R.color.ds_danger_on_container)
                )
                "medium" -> Triple(
                    UiColors.resolve(context, R.color.ds_warning_container),
                    UiColors.resolve(context, R.color.ds_warning),
                    UiColors.resolve(context, R.color.ds_warning_on_container)
                )
                "low" -> Triple(
                    UiColors.resolve(context, R.color.ds_success_container),
                    UiColors.resolve(context, R.color.ds_success),
                    UiColors.resolve(context, R.color.ds_success_on_container)
                )
                else -> Triple(
                    UiColors.resolve(context, R.color.ds_neutral_container),
                    UiColors.resolve(context, R.color.ds_border_strong),
                    UiColors.resolve(context, R.color.ds_text_secondary)
                )
            }
            holder.card.setCardBackgroundColor(bgColor)
            holder.card.strokeColor = strokeColor
            holder.card.strokeWidth = 2
            holder.tvSeverity.setTextColor(severityColor)
            holder.tvSeverity.setBackgroundColor(bgColor)

            // Icon based on type
            val icon = when (item.type) {
                "suspicious_attendance" -> "🕒"
                "rapid_deletion" -> "⚡"
                "perfect_attendance" -> "🎯"
                else -> "🔍"
            }
            holder.tvType.text = "$icon ${item.type}"
        }
    }
}
