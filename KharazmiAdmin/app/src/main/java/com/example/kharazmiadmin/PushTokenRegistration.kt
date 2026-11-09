package com.example.kharazmiadmin

import android.content.Context
import android.util.Log
import com.google.firebase.FirebaseApp
import com.google.firebase.FirebaseOptions
import com.google.firebase.messaging.FirebaseMessaging
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import retrofit2.http.Body
import retrofit2.http.POST

/** Authenticated registration for the current installation's FCM token. */
interface DeviceTokenApi {
    @POST("auth/device_token")
    suspend fun registerDeviceToken(@Body request: DeviceTokenRequest): SimpleResponse
}

object PushTokenRegistration {
    private const val PREFS_NAME = "PushRegistration"
    private const val KEY_FCM_TOKEN = "fcm_token"
    private const val TAG = "PushTokenRegistration"
    private val ioScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    /** Called after a successful login; the request is best-effort and never blocks sign-in. */
    fun refreshAndRegister(context: Context) {
        val appContext = context.applicationContext
        val firebaseApp = firebaseAppOrNull(appContext) ?: return
        try {
            FirebaseMessaging.getInstance(firebaseApp).token
                .addOnSuccessListener { token -> rememberAndRegister(appContext, token) }
                .addOnFailureListener { error ->
                    Log.w(TAG, "FCM token refresh failed; login remains available", error)
                }
        } catch (error: Exception) {
            Log.w(TAG, "FCM is unavailable; login remains available", error)
        }
    }

    /** Called by Firebase when a token rotates, including while the app is in the background. */
    fun onNewToken(context: Context, token: String) {
        rememberAndRegister(context.applicationContext, token)
    }

    /** Token is also passed to /auth/logout so the server removes only this device's registration. */
    fun currentToken(context: Context): String? = context.applicationContext
        .getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        .getString(KEY_FCM_TOKEN, null)
        ?.trim()
        ?.takeIf(String::isNotEmpty)

    private fun rememberAndRegister(context: Context, rawToken: String) {
        val token = rawToken.trim()
        if (token.isEmpty()) return
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY_FCM_TOKEN, token)
            .apply()
        registerForSignedInUser(context, token)
    }

    private fun registerForSignedInUser(context: Context, token: String) {
        if (SecureLoginStore.getToken(context).isBlank()) return
        ioScope.launch {
            // A logout may have completed between the FCM callback and this request.
            if (SecureLoginStore.getToken(context).isBlank()) return@launch
            try {
                RetrofitClient.getInstance(context)
                    .create(DeviceTokenApi::class.java)
                    .registerDeviceToken(DeviceTokenRequest(token))
            } catch (error: Exception) {
                Log.w(TAG, "Device-token registration failed; it will retry after the next login/token refresh", error)
            }
        }
    }

    /**
     * Supports either normal Firebase initialization or values supplied privately through Gradle
     * properties/environment. No project credentials are committed, and an unconfigured build is
     * still usable (push simply remains unavailable until configured).
     */
    private fun firebaseAppOrNull(context: Context): FirebaseApp? = try {
        FirebaseApp.getApps(context)
            .firstOrNull { it.name == FirebaseApp.DEFAULT_APP_NAME }
            ?: run {
                val apiKey = BuildConfig.FIREBASE_API_KEY.trim()
                val appId = BuildConfig.FIREBASE_APP_ID.trim()
                val projectId = BuildConfig.FIREBASE_PROJECT_ID.trim()
                val senderId = BuildConfig.FIREBASE_MESSAGING_SENDER_ID.trim()
                if (apiKey.isEmpty() || appId.isEmpty() || projectId.isEmpty() || senderId.isEmpty()) {
                    Log.i(TAG, "Firebase is not configured; provide the four FIREBASE_* build settings to enable push")
                    null
                } else {
                    val options = FirebaseOptions.Builder()
                        .setApiKey(apiKey)
                        .setApplicationId(appId)
                        .setProjectId(projectId)
                        .setGcmSenderId(senderId)
                        .build()
                    FirebaseApp.initializeApp(context, options)
                }
            }
    } catch (error: Exception) {
        Log.w(TAG, "Firebase initialization failed; push registration is skipped", error)
        null
    }
}

class PushMessagingService : com.google.firebase.messaging.FirebaseMessagingService() {
    override fun onNewToken(token: String) {
        super.onNewToken(token)
        PushTokenRegistration.onNewToken(applicationContext, token)
    }
}
