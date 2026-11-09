package com.example.kharazmiadmin

import android.content.Intent
import android.content.SharedPreferences
import android.content.Context
import android.os.Bundle
import android.text.Editable
import android.text.TextWatcher
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import android.widget.CheckBox
import androidx.appcompat.app.AlertDialog
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.google.android.material.floatingactionbutton.FloatingActionButton
import com.google.android.material.textfield.TextInputEditText
import com.google.android.material.chip.Chip
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import android.widget.Button
import android.content.res.ColorStateList

class ClassManagementActivity : BaseActivity() {

    private lateinit var rvClasses: RecyclerView
    private lateinit var adapter: ClassAdapter
    private var fullClassList: List<ClassListItem> = listOf()
    private var isAdminUser: Boolean = false

    // وضعیت انتخاب گروهی کلاس‌ها (جدید)
    private var isMultiSelectMode = false
    private val selectedClassIds = HashSet<Int>()
    private lateinit var llClassBulkContainer: LinearLayout
    private lateinit var btnBulkSuspend: Button
    private lateinit var fabAddClass: FloatingActionButton

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_class_management)

        // Check user role from SharedPreferences
        val prefs: SharedPreferences = getSharedPreferences("UserPrefs", Context.MODE_PRIVATE)
        val userRole = prefs.getString("USER_ROLE", "")
        
        val credsPrefs = getSharedPreferences("UserCreds", Context.MODE_PRIVATE)
        val subRole = credsPrefs.getString("USER_SUB_ROLE", "admin") ?: "admin"
        
        isAdminUser = userRole == "admin" && subRole == "admin"

        llClassBulkContainer = findViewById(R.id.llClassBulkContainer)
        btnBulkSuspend = findViewById(R.id.btnBulkSuspend)
        fabAddClass = findViewById(R.id.fabAddClass)

        // Setup List
        rvClasses = findViewById(R.id.rvClasses)
        rvClasses.layoutManager = LinearLayoutManager(this)

        // Add Button
        fabAddClass.setOnClickListener {
            val intent = Intent(this, AddClassActivity::class.java)
            startActivity(intent)
        }

        // Search Box
        val etSearch = findViewById<TextInputEditText>(R.id.etSearchClass)
        etSearch.addTextChangedListener(object : TextWatcher {
            override fun afterTextChanged(s: Editable?) {
                filterList(s.toString())
            }
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {}
        })

        // دکمه تعلیق گروهی کلاس‌ها (مخصوص ادمین ارشد)
        btnBulkSuspend.setOnClickListener {
            if (!isAdminUser) {
                Toast.makeText(this, getString(R.string.cmgmt_no_access), Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }

            if (selectedClassIds.isEmpty()) {
                Toast.makeText(this, getString(R.string.cmgmt_no_pick), Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }

            showBulkSuspendConfirmationDialog()
        }

        // Fetch Data
        fetchClasses()
    }

    override fun onResume() {
        super.onResume()
        resetMultiSelect()
        fetchClasses()
    }

    fun fetchClasses() {
        val retrofit = RetrofitClient.getInstance(this)
        val api = retrofit.create(ClassApi::class.java)

        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.

        lifecycleScope.launch(Dispatchers.IO) {
            try {
                fullClassList = api.getAllClasses()
                withContext(Dispatchers.Main) {
                    adapter = ClassAdapter(fullClassList)
                    rvClasses.adapter = adapter
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@ClassManagementActivity, getString(R.string.common_list_error), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    // صف تأیید ادمین: تصمیم گروهی با علت رد قابل audit است.
    private fun bulkApprove(courseIds: List<Int>) {
        lifecycleScope.launch(Dispatchers.IO) {
            RetrofitClient.getInstance(this@ClassManagementActivity).create(ClassApi::class.java)
                .bulkApprove(BulkClassDecisionRequest(courseIds))
            withContext(Dispatchers.Main) { fetchClasses() }
        }
    }

    private fun bulkReject(courseIds: List<Int>, rejectionReason: String) {
        lifecycleScope.launch(Dispatchers.IO) {
            RetrofitClient.getInstance(this@ClassManagementActivity).create(ClassApi::class.java)
                .bulkReject(BulkClassDecisionRequest(courseIds, rejectionReason))
            withContext(Dispatchers.Main) { fetchClasses() }
        }
    }

    // ویرایش زمان‌بندی/ظرفیت/انتقال معلم فقط از endpoint ادمین و با guardهای سرور.
    private fun updateClass(courseId: Int, request: AdminClassUpdateRequest) {
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                RetrofitClient.getInstance(this@ClassManagementActivity).create(ClassApi::class.java)
                    .updateClass(courseId, request)
                withContext(Dispatchers.Main) { fetchClasses() }
            } catch (error: Exception) {
                if (error is kotlinx.coroutines.CancellationException) throw error
                withContext(Dispatchers.Main) { Toast.makeText(this@ClassManagementActivity, "ویرایش کلاس انجام نشد", Toast.LENGTH_SHORT).show() }
            }
        }
    }

    private fun filterList(query: String) {
        if (!::adapter.isInitialized) return

        val filtered = fullClassList.filter {
            it.title.contains(query) || it.code.contains(query)
        }
        adapter.updateList(filtered)
    }

    private fun resetMultiSelect() {
        isMultiSelectMode = false
        selectedClassIds.clear()
        llClassBulkContainer.visibility = View.GONE
        fabAddClass.visibility = View.VISIBLE
    }

    private fun showBulkSuspendConfirmationDialog() {
        val count = selectedClassIds.size
        AlertDialog.Builder(this)
            .setTitle(getString(R.string.cmgmt_bulk_title))
            .setMessage(getString(R.string.cmgmt_bulk_msg, count))
            .setPositiveButton(getString(R.string.cmgmt_bulk_yes)) { _, _ ->
                performBulkClassSuspension()
            }
            .setNegativeButton(getString(R.string.action_cancel), null)
            .show()
    }

    private fun performBulkClassSuspension() {
        val retrofit = RetrofitClient.getInstance(this)
        val api = retrofit.create(ClassApi::class.java)

        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.

        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val res = api.suspendBulkClasses(BulkSuspendRequest(selectedClassIds.toList()))
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@ClassManagementActivity, getString(R.string.common_ok_msg, res.message), Toast.LENGTH_LONG).show()
                    resetMultiSelect()
                    fetchClasses()
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@ClassManagementActivity, getString(R.string.cmgmt_bulk_error), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    // --- List Adapter ---
    inner class ClassAdapter(private var classes: List<ClassListItem>) : RecyclerView.Adapter<ClassAdapter.ClassViewHolder>() {

        fun updateList(newList: List<ClassListItem>) {
            classes = newList
            notifyDataSetChanged()
        }

        inner class ClassViewHolder(view: View) : RecyclerView.ViewHolder(view) {
            val tvTitle: TextView = view.findViewById(R.id.tvClassTitle)
            val tvCode: TextView = view.findViewById(R.id.tvClassCode)
            val tvTeacher: TextView = view.findViewById(R.id.tvTeacherName)
            val tvGradeLevel: Chip = view.findViewById(R.id.chipGradeLevel)
            val tvGender: Chip = view.findViewById(R.id.chipGender)
            val tvSessionCount: Chip = view.findViewById(R.id.chipSessionCount)
            val llStudentPreview: LinearLayout = view.findViewById(R.id.ll_student_preview)
            val tvTeacherDebt: TextView = view.findViewById(R.id.tvTeacherDebt)
            val tvInstituteDebt: TextView = view.findViewById(R.id.tvInstituteDebt)
            val tvDebtNote: TextView = view.findViewById(R.id.tvDebtSessionsNote)
            val btnRegisterInvoice: Button = view.findViewById(R.id.btnRegisterInvoice)
            val btnSuspend: Button = view.findViewById(R.id.btnSuspend)
            val llTopStudents: LinearLayout = view.findViewById(R.id.ll_top_students)
            val tvTopStudents: TextView = view.findViewById(R.id.tvTopStudents)
            val cbSelectClass: CheckBox = view.findViewById(R.id.cbSelectClass)
        }

        private fun searchAndOpenStudentProfile(studentName: String, context: android.content.Context) {
            val intent = Intent(context, PersonListActivity::class.java)
            intent.putExtra("MODE", "STUDENT")
            intent.putExtra("SEARCH_QUERY", studentName)
            context.startActivity(intent)
        }

        override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ClassViewHolder {
            val view = LayoutInflater.from(parent.context).inflate(R.layout.item_class_row, parent, false)
            return ClassViewHolder(view)
        }

        override fun onBindViewHolder(holder: ClassViewHolder, position: Int) {
            val item = classes[position]
            holder.tvTitle.text = item.title
            holder.tvCode.text = getString(R.string.cmgmt_code_row, item.code)
            holder.tvGradeLevel.text = item.grade_level
            // سیستم برای کلاس جنسیت ثبت نمی‌کند؛ فقط چیپ همین بنر ادمین مخفی می‌شود.
            // مدل/endpoint مشترک دست‌نخورده می‌ماند تا پنل معلم رفتار ناخواسته نگیرد.
            holder.tvGender.text = ""
            holder.tvGender.visibility = View.GONE
            holder.tvSessionCount.text = getString(R.string.cmgmt_sessions_row, item.session_count)

            // اعمال رنگ پس‌زمینه کارت کلاس بر اساس bg_color ثبت شده
            if (!item.bg_color.isNullOrEmpty()) {
                try {
                    (holder.itemView as? com.google.android.material.card.MaterialCardView)?.setCardBackgroundColor(
                        android.graphics.Color.parseColor(item.bg_color)
                    )
                } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                    // رنگ نامعتبر رد می‌شود
                }
            }

            // بررسی فعال بودن حالت انتخاب چندتایی برای کلاس‌ها
            if (isMultiSelectMode && isAdminUser) {
                holder.cbSelectClass.visibility = View.VISIBLE
                holder.cbSelectClass.setOnCheckedChangeListener(null)
                holder.cbSelectClass.isChecked = selectedClassIds.contains(item.id)
                holder.cbSelectClass.setOnCheckedChangeListener { _, isChecked ->
                    if (isChecked) {
                        selectedClassIds.add(item.id)
                    } else {
                        selectedClassIds.remove(item.id)
                    }
                    btnBulkSuspend.text = getString(R.string.cmgmt_bulk_btn, selectedClassIds.size)
                }
                holder.btnSuspend.visibility = View.GONE
            } else {
                holder.cbSelectClass.visibility = View.GONE
                holder.btnSuspend.visibility = if (isAdminUser) View.VISIBLE else View.GONE
            }

            holder.tvTeacher.text = getString(R.string.cmgmt_teacher_row, item.teacher_name ?: getString(R.string.cmgmt_unknown))

            holder.llStudentPreview.removeAllViews()
            if (item.students_preview.isNotEmpty()) {
                item.students_preview.take(10).forEach { name ->
                    val tv = TextView(holder.itemView.context)
                    tv.text = getString(R.string.common_bullet_row, name)
                    tv.textSize = 12f
                    tv.setTextColor(UiColors.resolve(holder.itemView.context, R.color.text_primary))
                    tv.setPadding(0, 4, 0, 4)
                    tv.isClickable = true
                    tv.setOnClickListener {
                        searchAndOpenStudentProfile(name, holder.itemView.context)
                    }
                    holder.llStudentPreview.addView(tv)
                }
            } else {
                val tv = TextView(holder.itemView.context)
                tv.text = getString(R.string.cmgmt_no_students)
                tv.textSize = 10f
                tv.setTextColor(UiColors.resolve(holder.itemView.context, R.color.text_secondary))
                holder.llStudentPreview.addView(tv)
            }

            if (item.students_preview.isNotEmpty()) {
                holder.llTopStudents.visibility = View.VISIBLE
                val topStudentsText = item.students_preview.take(10).joinToString("\n") { getString(R.string.common_bullet_row, it) }
                holder.tvTopStudents.text = topStudentsText
                holder.tvTopStudents.setOnClickListener {
                    val intent = Intent(holder.itemView.context, ClassDetailActivity::class.java)
                    intent.putExtra("CLASS_ID", item.id)
                    holder.itemView.context.startActivity(intent)
                }
            } else {
                holder.llTopStudents.visibility = View.GONE
            }

            holder.tvTeacherDebt.text = String.format("%,d", item.debt_to_teacher)
            holder.tvInstituteDebt.text = String.format("%,d", item.debt_to_institute)
            ClassBannerNotes.bindDebtNote(
                holder.tvDebtNote, item.unpaid_sessions, item.sessions_billed, item.debt_to_teacher, item.debt_to_institute
            )

            // دکمه تعلیق تکی
            if (isAdminUser && !isMultiSelectMode) {
                holder.btnSuspend.visibility = View.VISIBLE
                if (item.is_suspended) {
                    holder.itemView.alpha = 0.5f
                    holder.btnSuspend.backgroundTintList = ColorStateList.valueOf(UiColors.resolve(holder.itemView.context, R.color.status_success))
                    holder.btnSuspend.text = getString(R.string.cmgmt_activate)
                } else {
                    holder.itemView.alpha = 1.0f
                    holder.btnSuspend.backgroundTintList = ColorStateList.valueOf(UiColors.resolve(holder.itemView.context, R.color.status_warning))
                    holder.btnSuspend.text = getString(R.string.cmgmt_suspend)
                }

                holder.btnSuspend.setOnClickListener {
                    val retrofit = RetrofitClient.getInstance(holder.itemView.context)
                    val api = retrofit.create(ClassApi::class.java)
                    // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
                    lifecycleScope.launch(Dispatchers.Main) {
                        try {
                            val response = withContext(Dispatchers.IO) { api.suspendClassAdmin(item.id) }
                            Toast.makeText(holder.itemView.context, response.message, Toast.LENGTH_SHORT).show()
                            fetchClasses()
                        } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                            Toast.makeText(holder.itemView.context, getString(R.string.cmgmt_suspend_error), Toast.LENGTH_SHORT).show()
                        }
                    }
                }
            } else {
                if (item.is_suspended) {
                    holder.itemView.alpha = 0.5f
                } else {
                    holder.itemView.alpha = 1.0f
                }
            }

            holder.btnRegisterInvoice.setOnClickListener {
                if (isMultiSelectMode) {
                    holder.cbSelectClass.isChecked = !holder.cbSelectClass.isChecked
                } else {
                    val intent = Intent(holder.itemView.context, InvoiceActivity::class.java)
                    intent.putExtra("CLASS_ID", item.id)
                    intent.putExtra("IS_ADMIN", true)
                    holder.itemView.context.startActivity(intent)
                }
            }

            holder.itemView.setOnClickListener {
                if (isMultiSelectMode) {
                    holder.cbSelectClass.isChecked = !holder.cbSelectClass.isChecked
                } else {
                    val intent = Intent(holder.itemView.context, ClassDetailActivity::class.java)
                    intent.putExtra("CLASS_ID", item.id)
                    holder.itemView.context.startActivity(intent)
                }
            }

            // کلیک طولانی (Long Click) برای فعال‌سازی حالت انتخاب چندتایی (تعلیق گروهی کلاس‌ها)
            holder.itemView.setOnLongClickListener {
                if (isAdminUser && !isMultiSelectMode) {
                    isMultiSelectMode = true
                    selectedClassIds.add(item.id)
                    
                    fabAddClass.visibility = View.GONE
                    llClassBulkContainer.visibility = View.VISIBLE
                    btnBulkSuspend.text = getString(R.string.cmgmt_bulk_btn_one)
                    
                    notifyDataSetChanged()
                    true
                } else {
                    false
                }
            }
        }

        override fun getItemCount() = classes.size
    }
}
