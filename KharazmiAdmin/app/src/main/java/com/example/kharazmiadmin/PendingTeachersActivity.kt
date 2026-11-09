package com.example.kharazmiadmin

import android.graphics.BitmapFactory
import android.os.Bundle
import android.util.Base64
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.ImageView
import android.widget.TextView
import android.widget.Toast
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path

// مدل داده معلم
data class TeacherPending(
    val id: Int,
    // FIX(null-data): لیست «در انتظار تایید» برای معلم بدون موبایل/نام ناقص null برمی‌گرداند —
    // null‌پذیر تا یک رکورد ناقص کل لیست را نشکند (fallback در adapter).
    val first_name: String? = null,
    val last_name: String? = null,
    val mobile: String? = null,
    val profile_image: String?,
    // FIX(teacher-approval): شعبه‌ی درخواست — سرور برای رکوردهای بدون انتساب null می‌دهد.
    @com.google.gson.annotations.SerializedName("branch_id") val branchId: Int? = null,
    @com.google.gson.annotations.SerializedName("branch_name") val branchName: String? = null
)

data class ApproveResponse(val message: String)

interface PendingApi {
    @GET("teachers/pending")
    suspend fun getPendingTeachers(): List<TeacherPending>

    @POST("teachers/approve/{id}")
    suspend fun approveTeacher(@Path("id") id: Int): ApproveResponse

    // ❌ متد جدید برای رد کردن (حذف) معلم
    @DELETE("teachers/reject/{id}")
    suspend fun rejectTeacher(@Path("id") id: Int): ApproveResponse
}

class PendingTeachersActivity : BaseActivity() {

    private lateinit var api: PendingApi
    private lateinit var rvPending: RecyclerView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_pending_teachers)

        rvPending = findViewById(R.id.rvPendingTeachers)
        rvPending.layoutManager = LinearLayoutManager(this)

        val retrofit = RetrofitClient.getInstance(this)
        api = retrofit.create(PendingApi::class.java)
    }

    // FIX(teacher-approval): دریافت لیست در onResume — بعد از ثبت معلم یا هر بار برگشت به این
    // صفحه، داده‌ی واقعی و تازه نشان داده می‌شود (قبلاً فقط یک‌بار در onCreate و بدون رفرش).
    override fun onResume() {
        super.onResume()
        fetchPendingList()
    }

    private fun fetchPendingList() {
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val list = api.getPendingTeachers()
                withContext(Dispatchers.Main) {
                    if (list.isEmpty()) {
                        // حالت empty: هم پیام روشن، هم لیست خالی (بدون ردیف قدیمی/گیج‌کننده)
                        Toast.makeText(this@PendingTeachersActivity, getString(R.string.ptch_empty), Toast.LENGTH_SHORT).show()
                    }
                    // 👇 حالا دو تا تابع به آداپتور پاس میدیم (تایید و رد)
                    rvPending.adapter = PendingAdapter(list,
                        onApproveClick = { teacherId -> approveTeacher(teacherId) },
                        onRejectClick = { teacherId -> rejectTeacher(teacherId) }
                    )
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                android.util.Log.e("PendingTeachersActivity", "fetchPendingList failed", e)
                withContext(Dispatchers.Main) {
                    // FIX(teacher-approval): خطای شبکه/سرور قبلاً فقط لاگ می‌شد و کاربر فکر می‌کرد
                    // «درخواستی وجود ندارد»؛ حالا خطای روشن نشان داده می‌شود و ردیف‌های قدیمی پاک می‌شوند.
                    Toast.makeText(this@PendingTeachersActivity, getString(R.string.ptch_load_error), Toast.LENGTH_LONG).show()
                    rvPending.adapter = PendingAdapter(emptyList(),
                        onApproveClick = { teacherId -> approveTeacher(teacherId) },
                        onRejectClick = { teacherId -> rejectTeacher(teacherId) }
                    )
                }
            }
        }
    }

    // تایید معلم
    private fun approveTeacher(teacherId: Int) {
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val res = api.approveTeacher(teacherId)
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@PendingTeachersActivity, getString(R.string.common_ok_msg, res.message), Toast.LENGTH_LONG).show()
                    
                    // ابطال کش لیست معلمان فعال
                    CacheManager.clearByPrefix(this@PendingTeachersActivity, "person_list_TEACHER")
                    
                    fetchPendingList() // رفرش لیست
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@PendingTeachersActivity, getString(R.string.ptch_op_error), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    // ❌ رد کردن معلم (حذف درخواست)
    private fun rejectTeacher(teacherId: Int) {
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val res = api.rejectTeacher(teacherId)
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@PendingTeachersActivity, getString(R.string.common_deleted_msg, res.message), Toast.LENGTH_LONG).show()
                    
                    // ابطال کش لیست معلمان فعال
                    CacheManager.clearByPrefix(this@PendingTeachersActivity, "person_list_TEACHER")
                    
                    fetchPendingList() // رفرش لیست
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@PendingTeachersActivity, getString(R.string.ptch_del_error), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }
}

// آداپتور آپدیت شده
class PendingAdapter(
    private val list: List<TeacherPending>,
    private val onApproveClick: (Int) -> Unit,
    private val onRejectClick: (Int) -> Unit // ✅ اضافه شده
) : RecyclerView.Adapter<PendingAdapter.VH>() {

    class VH(v: View) : RecyclerView.ViewHolder(v) {
        val name: TextView = v.findViewById(R.id.tvName)
        val mobile: TextView = v.findViewById(R.id.tvMobile)
        // FIX(teacher-approval): خط شعبه در کارت درخواست
        val branch: TextView = v.findViewById(R.id.tvBranch)
        val avatar: ImageView = v.findViewById(R.id.imgAvatar)
        val btnApprove: Button = v.findViewById(R.id.btnApprove)
        val btnReject: Button = v.findViewById(R.id.btnReject) // ✅ دکمه قرمز
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val v = LayoutInflater.from(parent.context).inflate(R.layout.item_pending, parent, false)
        return VH(v)
    }

    override fun onBindViewHolder(holder: VH, position: Int) {
        val item = list[position]
        // FIX(null-data): نام/موبایل ناقص نباید «null» نشان دهد یا binding را بشکند.
        val ctx = holder.itemView.context
        val displayName = "${item.first_name ?: ""} ${item.last_name ?: ""}".trim()
            .ifEmpty { ctx.getString(R.string.common_person_unknown) }
        holder.name.text = displayName
        holder.mobile.text = item.mobile ?: ""
        // FIX(teacher-approval): شعبه‌ی درخواست نمایش داده می‌شود؛ رکورد بدون انتساب → «بدون شعبه»
        holder.branch.text = ctx.getString(
            R.string.ptch_branch_row,
            item.branchName?.takeIf { it.isNotBlank() } ?: ctx.getString(R.string.ptch_no_branch)
        )

        if (item.profile_image != null) {
            try {
                val imageBytes = Base64.decode(item.profile_image, Base64.DEFAULT)
                val decodedImage = BitmapFactory.decodeByteArray(imageBytes, 0, imageBytes.size)
                holder.avatar.setImageBitmap(decodedImage)
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e; }
        }

        // کلیک روی تایید
        holder.btnApprove.setOnClickListener {
            onApproveClick(item.id)
        }

        // کلیک روی رد کردن
        holder.btnReject.setOnClickListener {
            onRejectClick(item.id)
        }
    }

    override fun getItemCount() = list.size
}
