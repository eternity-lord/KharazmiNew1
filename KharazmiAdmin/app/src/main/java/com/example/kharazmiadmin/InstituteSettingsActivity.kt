package com.example.kharazmiadmin

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.widget.ImageView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.lifecycle.lifecycleScope
import com.bumptech.glide.Glide
import com.google.android.material.button.MaterialButton
import com.google.android.material.textfield.TextInputEditText
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.PUT

// API Interface
interface InstituteSettingsApi {
    @GET("admin/institute_settings")
    suspend fun getSettings(): InstituteSettings

    @PUT("admin/institute_settings")
    suspend fun updateSettings(@Body data: InstituteSettings): SimpleResponse

    @retrofit2.http.Multipart
    @POST("admin/institute_settings/upload_logo")
    suspend fun uploadLogo(
        @retrofit2.http.Part file: okhttp3.MultipartBody.Part
    ): SimpleResponse
}

class InstituteSettingsActivity : BaseActivity() {

    private lateinit var etName: TextInputEditText
    private lateinit var etPhone: TextInputEditText
    private lateinit var etEmail: TextInputEditText
    private lateinit var etAddress: TextInputEditText
    private lateinit var etLiveMaxMinutes: TextInputEditText
    private lateinit var etTeacherSettlementAlertDays: TextInputEditText
    private lateinit var imgLogo: ImageView
    private lateinit var btnSave: MaterialButton

    private lateinit var api: InstituteSettingsApi
    private var cachedSettings: InstituteSettings? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_institute_settings)

        initViews()
        setupApi()
        fetchSettings()
    }

    private fun initViews() {
        etName = findViewById(R.id.etName)
        etPhone = findViewById(R.id.etPhone)
        etEmail = findViewById(R.id.etEmail)
        etAddress = findViewById(R.id.etAddress)
        etLiveMaxMinutes = findViewById(R.id.etLiveMaxMinutes)
        etTeacherSettlementAlertDays = findViewById(R.id.etTeacherSettlementAlertDays)
        imgLogo = findViewById(R.id.imgLogo)
        btnSave = findViewById(R.id.btnSave)

        imgLogo.setOnClickListener {
            showImageSelectDialog()
        }

        btnSave.setOnClickListener {
            saveSettings()
        }
    }

    private fun setupApi() {
        val retrofit = RetrofitClient.getInstance(this)
        api = retrofit.create(InstituteSettingsApi::class.java)
    }

    private fun fetchSettings() {
        val cacheKey = "institute_settings"
        val type = object : com.google.gson.reflect.TypeToken<InstituteSettings>() {}.type

        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.

        lifecycleScope.launch(Dispatchers.Main) {
            CachedApiCall.execute(
                context = this@InstituteSettingsActivity,
                cacheKey = cacheKey,
                type = type,
                networkCall = { api.getSettings() },
                onSuccess = { data, isOffline, timestamp ->
                    cachedSettings = data
                    etName.setText(data.name)
                    etPhone.setText(data.phone)
                    etEmail.setText(data.official_email ?: "")
                    etAddress.setText(data.address)
                    etLiveMaxMinutes.setText((data.liveSessionMaxMinutes ?: 180).toString())
                    etTeacherSettlementAlertDays.setText(
                        (data.teacherSettlementAlertDays ?: 30).toString()
                    )

                    if (!data.logo_path.isNullOrEmpty()) {
                        val baseUrl = RetrofitClient.getInstance(this@InstituteSettingsActivity).baseUrl().toString()
                        val imgUrl = baseUrl + "uploads/profiles/" + data.logo_path
                        val glideAuthToken = SecureLoginStore.getToken(this@InstituteSettingsActivity)  // FIX M22.
                        // FIX M3: Glide با هدر احراز (اندپوینت /uploads دیگر عمومی نیست).
                        val glideUrl = com.bumptech.glide.load.model.GlideUrl(
                            imgUrl,
                            com.bumptech.glide.load.model.LazyHeaders.Builder()
                                .addHeader("Authorization", "Bearer $glideAuthToken")
                                .build()
                        )
                        Glide.with(this@InstituteSettingsActivity)
                            .load(glideUrl)
                            .placeholder(android.R.drawable.sym_def_app_icon)
                            .error(android.R.drawable.sym_def_app_icon)
                            .centerCrop()
                            .into(imgLogo)
                    }

                    if (isOffline) {
                        CachedApiCall.showOfflineBanner(this@InstituteSettingsActivity, timestamp)
                    } else {
                        CachedApiCall.hideOfflineBanner(this@InstituteSettingsActivity)
                    }
                },
                onFailure = {
                    Toast.makeText(this@InstituteSettingsActivity, getString(R.string.iset_load_error), Toast.LENGTH_SHORT).show()
                }
            )
        }
    }

    private fun saveSettings() {
        val name = etName.text.toString().trim()
        val phone = etPhone.text.toString().trim()
        val email = etEmail.text.toString().trim()
        val address = etAddress.text.toString().trim()

        if (name.isEmpty() || phone.isEmpty() || address.isEmpty()) {
            Toast.makeText(this, getString(R.string.iset_fill), Toast.LENGTH_SHORT).show()
            return
        }

        val liveMax = etLiveMaxMinutes.text.toString().trim().toIntOrNull() ?: 180
        val settlementAlertDays =
            etTeacherSettlementAlertDays.text.toString().trim().toIntOrNull() ?: 30
        if (settlementAlertDays !in 1..3650) {
            Toast.makeText(
                this,
                getString(R.string.iset_warn_range),
                Toast.LENGTH_SHORT
            ).show()
            return
        }

        val data = InstituteSettings(
            id = cachedSettings?.id ?: 1,
            name = name,
            phone = phone,
            address = address,
            official_email = email,
            logo_path = cachedSettings?.logo_path,
            liveSessionMaxMinutes = liveMax,
            teacherSettlementAlertDays = settlementAlertDays
        )

        btnSave.isEnabled = false
        btnSave.text = getString(R.string.iset_saving)

        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.

        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val res = api.updateSettings(data)
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@InstituteSettingsActivity, getString(R.string.common_ok_msg, res.message), Toast.LENGTH_LONG).show()
                    
                    // ابطال کامل کش تنظیمات
                    CacheManager.clear(this@InstituteSettingsActivity, "institute_settings")
                    CacheManager.clearByPrefix(
                        this@InstituteSettingsActivity,
                        "today_summary_admin_"
                    )
                    
                    btnSave.isEnabled = true
                    btnSave.text = getString(R.string.iset_save)
                    
                    fetchSettings() // لود مجدد
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@InstituteSettingsActivity, getString(R.string.iset_save_error), Toast.LENGTH_SHORT).show()
                    btnSave.isEnabled = true
                    btnSave.text = getString(R.string.iset_save)
                }
            }
        }
    }

    // --- مدیریت بارگذاری لوگو ---
    private fun showImageSelectDialog() {
        val options = arrayOf(getString(R.string.iset_opt_camera), getString(R.string.iset_opt_gallery))
        AlertDialog.Builder(this)
            .setTitle(getString(R.string.iset_logo_title))
            .setItems(options) { _, which ->
                if (which == 0) {
                    if (checkSelfPermission(android.Manifest.permission.CAMERA) != android.content.pm.PackageManager.PERMISSION_GRANTED) {
                        requestPermissions(arrayOf(android.Manifest.permission.CAMERA), 101)
                    } else {
                        openCamera()
                    }
                } else {
                    openGallery()
                }
            }
            .show()
    }

    private fun openGallery() {
        val intent = Intent(Intent.ACTION_PICK)
        intent.type = "image/*"
        startActivityForResult(intent, 201)
    }

    private fun openCamera() {
        val intent = Intent(android.provider.MediaStore.ACTION_IMAGE_CAPTURE)
        startActivityForResult(intent, 202)
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == 101 && grantResults.isNotEmpty() && grantResults[0] == android.content.pm.PackageManager.PERMISSION_GRANTED) {
            openCamera()
        } else {
            Toast.makeText(this, getString(R.string.iset_no_camera), Toast.LENGTH_SHORT).show()
        }
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (resultCode == RESULT_OK) {
            if (requestCode == 201) { // Gallery
                val uri = data?.data
                if (uri != null) {
                    uploadImageUri(uri)
                }
            } else if (requestCode == 202) { // Camera
                val bitmap = data?.extras?.get("data") as? android.graphics.Bitmap
                if (bitmap != null) {
                    uploadImageBitmap(bitmap)
                }
            }
        }
    }

    private fun uploadImageUri(uri: Uri) {
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val inputStream = contentResolver.openInputStream(uri)
                val file = java.io.File(cacheDir, "temp_logo.jpg")
                val outputStream = java.io.FileOutputStream(file)
                inputStream?.copyTo(outputStream)
                outputStream.flush()
                outputStream.close()
                inputStream?.close()
                
                uploadFileToServer(file)
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@InstituteSettingsActivity, getString(R.string.iset_img_error), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun uploadImageBitmap(bitmap: android.graphics.Bitmap) {
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val file = java.io.File(cacheDir, "temp_logo.jpg")
                val outputStream = java.io.FileOutputStream(file)
                bitmap.compress(android.graphics.Bitmap.CompressFormat.JPEG, 90, outputStream)
                outputStream.flush()
                outputStream.close()
                
                uploadFileToServer(file)
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@InstituteSettingsActivity, getString(R.string.iset_img_error), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun uploadFileToServer(file: java.io.File) {
        val requestFile = okhttp3.RequestBody.create(okhttp3.MediaType.parse("image/*"), file)
        val body = okhttp3.MultipartBody.Part.createFormData("file", file.name, requestFile)
        
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val response = api.uploadLogo(body)
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@InstituteSettingsActivity, getString(R.string.common_ok_msg, response.message), Toast.LENGTH_SHORT).show()
                    
                    // ابطال کش تنظیمات
                    CacheManager.clear(this@InstituteSettingsActivity, "institute_settings")
                    
                    fetchSettings() // رفرش خودکار لوگو
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@InstituteSettingsActivity, getString(R.string.iset_upload_error), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }
}
