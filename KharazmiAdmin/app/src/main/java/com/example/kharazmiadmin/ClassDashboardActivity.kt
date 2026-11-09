package com.example.kharazmiadmin

import android.content.Intent
import android.os.Bundle
import android.widget.TextView
import android.widget.Toast
import com.google.android.material.card.MaterialCardView
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class ClassDashboardActivity : BaseActivity() {

    private var classId: Int = -1
    private var className: String = ""
    private var isSuspended: Boolean = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_class_dashboard)

        classId = intent.getIntExtra("CLASS_ID", -1)
        className = intent.getStringExtra("CLASS_NAME") ?: ""
        isSuspended = intent.getBooleanExtra("IS_SUSPENDED", false)

        findViewById<TextView>(R.id.tvClassName).text = getString(R.string.cdash_mgmt_title, className)

        // Check if class is suspended
        if (isSuspended) {
            Toast.makeText(this, getString(R.string.common_class_activate), Toast.LENGTH_LONG).show()
            disableAllButtons()
        }

        // 1. دکمه جلسه جدید -> میره به همون AttendanceActivity ولی با حالت جدید
        findViewById<MaterialCardView>(R.id.btnNewSession).setOnClickListener {
            if (isSuspended) {
                Toast.makeText(this, getString(R.string.common_class_activate), Toast.LENGTH_LONG).show()
                return@setOnClickListener
            }
            val intent = Intent(this, AttendanceActivity::class.java)
            intent.putExtra("TARGET_COURSE_ID", classId)
            intent.putExtra("TARGET_COURSE_NAME", className)
            // یک فلگ میفرستیم که بدونه باید جلسه جدید بسازه
            intent.putExtra("MODE", "NEW_SESSION")
            startActivity(intent)
        }

        // 2. دکمه تاریخچه جلسات (بعدا میسازیم)
        findViewById<MaterialCardView>(R.id.btnSessionHistory).setOnClickListener {
            if (isSuspended) {
                Toast.makeText(this, getString(R.string.common_class_activate), Toast.LENGTH_LONG).show()
                return@setOnClickListener
            }
            val intent = Intent(this, SessionHistoryActivity::class.java)
            intent.putExtra("CLASS_ID", classId)
            startActivity(intent)
        }

        // 3. دکمه لیست دانش‌آموزان -> میره به همون ClassSetupActivity ولی فقط برای نمایش
        findViewById<MaterialCardView>(R.id.btnStudentList).setOnClickListener {
            if (isSuspended) {
                Toast.makeText(this, getString(R.string.common_class_activate), Toast.LENGTH_LONG).show()
                return@setOnClickListener
            }
            val intent = Intent(this, ClassSetupActivity::class.java)
            intent.putExtra("CLASS_ID", classId)
            intent.putExtra("CLASS_NAME", className)
            startActivity(intent)
        }

        // 4. دکمه مالی (بعدا میسازیم)
        findViewById<MaterialCardView>(R.id.btnFinancial).setOnClickListener {
            if (isSuspended) {
                Toast.makeText(this, getString(R.string.common_class_activate), Toast.LENGTH_LONG).show()
                return@setOnClickListener
            }
            Toast.makeText(this, getString(R.string.cdash_fin_todo), Toast.LENGTH_SHORT).show()
        }
    }

    private fun disableAllButtons() {
        findViewById<MaterialCardView>(R.id.btnNewSession).isEnabled = false
        findViewById<MaterialCardView>(R.id.btnNewSession).alpha = 0.5f

        findViewById<MaterialCardView>(R.id.btnSessionHistory).isEnabled = false
        findViewById<MaterialCardView>(R.id.btnSessionHistory).alpha = 0.5f

        findViewById<MaterialCardView>(R.id.btnStudentList).isEnabled = false
        findViewById<MaterialCardView>(R.id.btnStudentList).alpha = 0.5f

        findViewById<MaterialCardView>(R.id.btnFinancial).isEnabled = false
        findViewById<MaterialCardView>(R.id.btnFinancial).alpha = 0.5f
    }
}
