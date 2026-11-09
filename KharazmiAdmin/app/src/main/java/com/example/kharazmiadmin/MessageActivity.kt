package com.example.kharazmiadmin

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.view.Gravity
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

// API Models for Messenger
data class ConversationItem(
    val id: Int,
    val title: String,
    val type: String,
    val last_message: String,
    val last_time: String,
    val is_pinned: Boolean
)

data class MessageHistoryItem(
    val id: Int,
    val sender_id: Int,
    val sender_role: String,
    val body: String,
    val attachment: String?,
    val created_at: String
)

data class ConversationCreateRequest(
    val title: String?,
    val type: String,
    val participant_ids: List<Int>,
    val participant_roles: List<String>
)

data class MessageSendRequest(
    val body: String
)

data class BroadcastMessageRequest(
    val target_type: String,
    val target_id: Int?,
    val body: String
)

data class PinToggleRequest(
    val pinned: Boolean
)

data class PinToggleResponse(
    val is_pinned: Boolean
)

interface MessageApi {
    @GET("messages/conversations")
    suspend fun getConversations(): List<ConversationItem>

    @POST("messages/conversations/create")
    suspend fun createConversation(@Body req: ConversationCreateRequest): SimpleResponse

    @GET("messages/conversations/{id}/history")
    suspend fun getHistory(@Path("id") id: Int): List<MessageHistoryItem>

    @POST("messages/conversations/{id}/send")
    suspend fun sendMessage(@Path("id") id: Int, @Body req: MessageSendRequest): SimpleResponse

    @POST("messages/broadcast")
    suspend fun sendBroadcast(@Body req: BroadcastMessageRequest): SimpleResponse

    @POST("messages/conversations/{id}/pin")
    suspend fun setPin(@Path("id") id: Int, @Body req: PinToggleRequest): PinToggleResponse
}

class MessageActivity : BaseActivity() {

    private lateinit var flipper: ViewFlipper
    private lateinit var rvConversations: RecyclerView
    private lateinit var cardBroadcast: MaterialCardView
    private lateinit var etBroadcast: TextInputEditText
    private lateinit var btnBroadcast: Button

    // Chat Details views
    private lateinit var rvHistory: RecyclerView
    private lateinit var etCompose: TextInputEditText
    private lateinit var btnSend: Button
    private lateinit var btnBack: Button

    private lateinit var api: MessageApi
    private var role: String = "student"
    private var currentUserId: Int = -1
    private var activeConversationId: Int = -1
    private var convAdapter: ConversationAdapter? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_message_list)

        val credsPrefs = getSharedPreferences("UserCreds", Context.MODE_PRIVATE)
        role = credsPrefs.getString("USER_SUB_ROLE", "student") ?: "student"
        currentUserId = credsPrefs.getInt("USER_ID", -1)

        initViews()
        setupApi()
        setupListeners()
        loadConversations()
    }

    private fun initViews() {
        flipper = findViewById(R.id.messageFlipper)
        rvConversations = findViewById(R.id.rvConversations)
        cardBroadcast = findViewById(R.id.cardBroadcastMessage)
        etBroadcast = findViewById(R.id.etBroadcastBody)
        btnBroadcast = findViewById(R.id.btnSubmitBroadcast)

        rvHistory = findViewById(R.id.rvChatHistory)
        etCompose = findViewById(R.id.etComposeMessage)
        btnSend = findViewById(R.id.btnSendMessage)
        btnBack = findViewById(R.id.btnBackToInbox)

        rvConversations.layoutManager = LinearLayoutManager(this)
        rvHistory.layoutManager = LinearLayoutManager(this)

        if (role in listOf("admin", "teacher")) {
            cardBroadcast.visibility = View.VISIBLE
        } else {
            cardBroadcast.visibility = View.GONE
        }
    }

    private fun setupApi() {
        val retrofit = RetrofitClient.getInstance(this)
        api = retrofit.create(MessageApi::class.java)
    }

    private fun setupListeners() {
        btnBack.setOnClickListener {
            flipper.displayedChild = 0 // Return to Inbox
            loadConversations()
        }

        btnSend.setOnClickListener {
            val text = etCompose.text.toString().trim()
            if (text.isNotEmpty() && activeConversationId != -1) {
                sendMessageToServer(text)
            }
        }

        btnBroadcast.setOnClickListener {
            val text = etBroadcast.text.toString().trim()
            if (text.isNotEmpty()) {
                sendBroadcastOnServer(text)
            } else {
                Toast.makeText(this, getString(R.string.msg_empty), Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun loadConversations() {
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val list = api.getConversations()
                withContext(Dispatchers.Main) {
                    if (list.isEmpty()) {
                        Toast.makeText(this@MessageActivity, getString(R.string.msg_no_conv), Toast.LENGTH_SHORT).show()
                    }
                    convAdapter = ConversationAdapter(
                        list,
                        onClick = { conv -> openConversationDetails(conv.id, conv.title) },
                        onLongClick = { conv -> togglePin(conv) }
                    )
                    rvConversations.adapter = convAdapter
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@MessageActivity, getString(R.string.msg_inbox_error), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    // FIX (H2/pin-app): long-press روی گفتگو → تاگل پین؛ فقط همان آیتم آپدیت می‌شود (بدون رفرش کامل).
    private fun togglePin(conv: ConversationItem) {
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val res = api.setPin(conv.id, PinToggleRequest(!conv.is_pinned))
                withContext(Dispatchers.Main) {
                    convAdapter?.updatePin(conv.id, res.is_pinned)
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@MessageActivity, getString(R.string.msg_pin_error), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun openConversationDetails(conversationId: Int, title: String) {
        activeConversationId = conversationId
        flipper.displayedChild = 1 // Switch to Chat details flipper
        findViewById<TextView>(R.id.tvMessageTitle).text = title
        loadChatHistory()
    }

    private fun loadChatHistory() {
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val msgs = api.getHistory(activeConversationId)
                withContext(Dispatchers.Main) {
                    rvHistory.adapter = ChatAdapter(msgs, currentUserId, role)
                    rvHistory.scrollToPosition(msgs.size - 1)
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@MessageActivity, getString(R.string.msg_list_error), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun messageError(error: Exception, fallback: String): String {
        if (error is HttpException) {
            val raw = error.response()?.errorBody()?.string()
            val detail = try {
                org.json.JSONObject(raw ?: "").optString("detail")
            } catch (_: Exception) { "" }
            return detail.ifBlank { "$fallback (${error.code()})" }
        }
        return error.message?.takeIf { it.isNotBlank() } ?: fallback
    }

    private fun sendMessageToServer(body: String) {
        btnSend.isEnabled = false  // FIX L9: ضد دابل‌کلیک.
        val req = MessageSendRequest(body)
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val response = api.sendMessage(activeConversationId, req)
                withContext(Dispatchers.Main) {
                    etCompose.text = null
                    btnSend.isEnabled = true
                    Toast.makeText(this@MessageActivity, response.message, Toast.LENGTH_SHORT).show()
                    loadChatHistory() // Reload
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    val detail = messageError(e, getString(R.string.msg_send_error))
                    Toast.makeText(this@MessageActivity, detail, Toast.LENGTH_LONG).show()
                    btnSend.isEnabled = true
                }
            }
        }
    }

    private fun sendBroadcastOnServer(body: String) {
        btnBroadcast.isEnabled = false  // FIX L9: ضد دابل‌کلیک (اطلاعیه تکراری).
        val target = if (role == "admin") "everyone" else "class"
        val req = BroadcastMessageRequest(target, null, body)
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val response = api.sendBroadcast(req)
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@MessageActivity, response.message, Toast.LENGTH_LONG).show()
                    etBroadcast.text = null
                    btnBroadcast.isEnabled = true
                    loadConversations() // Reload list
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    val detail = messageError(e, getString(R.string.msg_group_error))
                    Toast.makeText(this@MessageActivity, detail, Toast.LENGTH_LONG).show()
                    btnBroadcast.isEnabled = true
                }
            }
        }
    }
}

class ConversationAdapter(
    list: List<ConversationItem>,
    private val onClick: (ConversationItem) -> Unit,
    private val onLongClick: (ConversationItem) -> Unit
) : RecyclerView.Adapter<ConversationAdapter.VH>() {

    private val items = list.toMutableList()

    fun updatePin(conversationId: Int, pinned: Boolean) {
        val i = items.indexOfFirst { it.id == conversationId }
        if (i != -1) {
            items[i] = items[i].copy(is_pinned = pinned)
            notifyItemChanged(i)
        }
    }

    class VH(v: View) : RecyclerView.ViewHolder(v) {
        val title: TextView = v.findViewById(R.id.tvConvTitle)
        val msg: TextView = v.findViewById(R.id.tvConvLastMessage)
        val time: TextView = v.findViewById(R.id.tvConvTime)
        val pin: ImageView = v.findViewById(R.id.imgPinned)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val v = LayoutInflater.from(parent.context).inflate(R.layout.item_conversation, parent, false)
        return VH(v)
    }

    override fun onBindViewHolder(holder: VH, position: Int) {
        val item = items[position]
        holder.title.text = item.title
        holder.msg.text = item.last_message
        holder.time.text = item.last_time

        if (item.is_pinned) {
            holder.pin.visibility = View.VISIBLE
        } else {
            holder.pin.visibility = View.GONE
        }

        holder.itemView.setOnClickListener { onClick(item) }
        holder.itemView.setOnLongClickListener { onLongClick(item); true }
    }

    override fun getItemCount() = items.size
}

class ChatAdapter(
    private val list: List<MessageHistoryItem>,
    private val currentUserId: Int,
    private val currentRole: String
) : RecyclerView.Adapter<ChatAdapter.VH>() {

    class VH(v: View) : RecyclerView.ViewHolder(v) {
        val bubble: MaterialCardView = v.findViewById(R.id.cardMessageBubble)
        val text: TextView = v.findViewById(R.id.tvMessageText)
        val time: TextView = v.findViewById(R.id.tvMessageTime)
        val container: View = bubble.parent as View // FIX: Reuse the typed bubble binding; avoid an uninferable generic view lookup.
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val v = LayoutInflater.from(parent.context).inflate(R.layout.item_chat_message, parent, false)
        return VH(v)
    }

    override fun onBindViewHolder(holder: VH, position: Int) {
        val item = list[position]
        holder.text.text = item.body
        holder.time.text = item.created_at

        // Align bubble layout based on sender identity
        val isSelf = item.sender_id == currentUserId && item.sender_role.lowercase() == currentRole.lowercase()
        val params = holder.bubble.layoutParams as LinearLayout.LayoutParams
        
        if (isSelf) {
            params.gravity = Gravity.LEFT // Incoming-style for Persian layout
            // FIX: Opaque muted gold with readable light text, matching bg_chat_sent.
            holder.bubble.setCardBackgroundColor(androidx.core.content.ContextCompat.getColor(holder.bubble.context, R.color.gold_chat_sent_bg))
        } else {
            params.gravity = Gravity.RIGHT
            // FIX: Keep incoming bubbles on a dark Gold surface too; the existing text is light.
            holder.bubble.setCardBackgroundColor(androidx.core.content.ContextCompat.getColor(holder.bubble.context, R.color.gold_bg_elevated))
        }
        // FIX: A subtle border distinguishes opaque sent bubbles without lowering text/view opacity.
        holder.bubble.strokeWidth = holder.bubble.resources.displayMetrics.density.toInt().coerceAtLeast(1)
        holder.bubble.strokeColor = androidx.core.content.ContextCompat.getColor(holder.bubble.context, if (isSelf) R.color.gold_primary_dark else R.color.gold_border_subtle)
        holder.bubble.layoutParams = params
    }

    override fun getItemCount() = list.size
}
