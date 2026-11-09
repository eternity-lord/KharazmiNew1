package com.example.kharazmiadmin

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import java.io.IOException

// FIX: Android credential leftover - passwords are encrypted with a Keystore-backed key, never session prefs.
object SecureLoginStore {
    const val FILE_NAME = "SecureLoginCreds"

    // FIX: A forced credential reset must clear the encrypted store as well as the old session preferences.
    fun clear(context: Context) {
        context.applicationContext.deleteSharedPreferences(FILE_NAME)
        cachedEncrypted = null  // FIX M22: حذف فایل بدون ابطال کش، توکن قدیمی را از حافظه زنده نگه می‌داشت.
    }

    fun open(context: Context): SharedPreferences {
        val appContext = context.applicationContext
        val masterKey = MasterKey.Builder(appContext)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()
        val encrypted = EncryptedSharedPreferences.create(
            appContext,
            FILE_NAME,
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
        )
        val legacy = appContext.getSharedPreferences("UserCreds", Context.MODE_PRIVATE)
        val password = legacy.getString("SAVED_PASS", null)
        if (password != null) {
            // FIX: Commit encrypted migration before removing the old plaintext; failures disable remembering login.
            if (!encrypted.edit()
                    .putString("SAVED_MOBILE", legacy.getString("SAVED_MOBILE", ""))
                    .putString("SAVED_PASS", password)
                    .commit()) throw IOException("Unable to persist encrypted login")
            if (!legacy.edit().remove("SAVED_PASS").commit()) throw IOException("Unable to remove legacy login")
        }
        return encrypted
    }

    // FIX M22: توکن سشن فقط رمزشده (Keystore) نگه‌داری می‌شود، نه plaintext در UserCreds.
    private const val KEY_TOKEN = "USER_TOKEN"

    // FIX M22: ساخت EncryptedSharedPreferences سنگین است (MasterKey) — یک‌بار کش می‌شود تا
    // اینترسپتور Retrofit در هر ریکوئست آن را نسازد.
    @Volatile private var cachedEncrypted: SharedPreferences? = null

    private fun encrypted(context: Context): SharedPreferences {
        cachedEncrypted?.let { return it }
        return synchronized(this) {
            cachedEncrypted ?: run {
                val prefs = open(context.applicationContext)
                migrateLegacyToken(context.applicationContext, prefs)
                cachedEncrypted = prefs
                prefs
            }
        }
    }

    private fun migrateLegacyToken(appContext: Context, encrypted: SharedPreferences) {
        val legacy = appContext.getSharedPreferences("UserCreds", Context.MODE_PRIVATE)
        val token = legacy.getString(KEY_TOKEN, null)
        if (!token.isNullOrEmpty() && !encrypted.contains(KEY_TOKEN)) {
            // FIX M22: اول commit رمزشده، بعد پاک‌سازی plaintext (مثل مهاجرت SAVED_PASS).
            if (encrypted.edit().putString(KEY_TOKEN, token).commit())
                legacy.edit().remove(KEY_TOKEN).apply()
        } else if (!token.isNullOrEmpty()) {
            legacy.edit().remove(KEY_TOKEN).apply()  // نسخه‌ی رمزشده موجود است؛ plaintext تکراری پاک می‌شود.
        }
    }

    fun saveToken(context: Context, token: String) {
        if (!encrypted(context).edit().putString(KEY_TOKEN, token).commit())
            throw IOException("Unable to persist encrypted session token")
        // هیچ fallback به plaintext نیست — بقایای احتمالی توکن plaintext هم پاک می‌شود.
        context.applicationContext.getSharedPreferences("UserCreds", Context.MODE_PRIVATE)
            .edit().remove(KEY_TOKEN).apply()
    }

    fun getToken(context: Context): String = try {
        encrypted(context).getString(KEY_TOKEN, "") ?: ""
    } catch (error: Exception) {
        android.util.Log.w("SecureLoginStore", "encrypted token unreadable; treating as logged out", error)
        ""
    }

    fun clearToken(context: Context) {
        try {
            encrypted(context).edit().remove(KEY_TOKEN).apply()
        } catch (ignored: Exception) {
        }
        context.applicationContext.getSharedPreferences("UserCreds", Context.MODE_PRIVATE)
            .edit().remove(KEY_TOKEN).apply()
    }
}

