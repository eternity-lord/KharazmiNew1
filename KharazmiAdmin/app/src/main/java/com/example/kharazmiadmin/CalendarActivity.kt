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
import retrofit2.http.*
import java.text.DecimalFormat

// API Models for Calendar
data class RoomCreateRequest(
    val name: String,
    val capacity: Int,
    val location: String,
    val equipment: String? = null
)

data class RoomItem(
    val id: Int,
    val name: String,
    val capacity: Int,
    val location: String,
    val equipment: String?,
    val active: Boolean
)

data class CalendarEventItem(
    val type: String,
    val title: String,
    val detail: String,
    val schedule: String
)

data class ConflictCheckRequest(
    val teacher_id: Int,
    val room_id: Int?,
    val days_of_week: String,
    val class_time: String,
    val student_ids: List<Int> = emptyList()
)

data class ConflictCheckResponse(
    val has_conflict: Boolean,
    val message: String,
    val details: List<String>
)

interface CalendarApi {
    @POST("rooms/create")
    suspend fun createRoom(@Body req: RoomCreateRequest): RoomItem

    @GET("rooms/list")
    suspend fun getRoomsList(): List<RoomItem>

    @POST("calendar/check_conflicts")
    suspend fun checkConflicts(@Body req: ConflictCheckRequest): ConflictCheckResponse

    @GET("calendar/events")
    suspend fun getCalendarEvents(): List<CalendarEventItem>
}

class CalendarActivity : BaseActivity() {

    private lateinit var flipper: ViewFlipper
    private lateinit var rvEvents: RecyclerView
    private lateinit var btnCheckConflicts: Button
    private lateinit var btnManageRooms: Button

    // Room State Views
    private lateinit var cardAddRoom: MaterialCardView
    private lateinit var etRoomName: TextInputEditText
    private lateinit var etRoomCapacity: TextInputEditText
    private lateinit var etRoomLocation: TextInputEditText
    private lateinit var btnSubmitRoom: Button
    private lateinit var rvRooms: RecyclerView
    private lateinit var btnBack: Button

    private lateinit var api: CalendarApi
    private var role: String = "student"

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_calendar)

        val credsPrefs = getSharedPreferences("UserCreds", Context.MODE_PRIVATE)
        role = credsPrefs.getString("USER_SUB_ROLE", "admin") ?: "admin"

        initViews()
        setupApi()
        setupListeners()
        loadEvents()
    }

    private fun initViews() {
        flipper = findViewById(R.id.calendarFlipper)
        rvEvents = findViewById(R.id.rvEvents)
        btnCheckConflicts = findViewById(R.id.btnCheckConflicts)
        btnManageRooms = findViewById(R.id.btnManageRooms)

        cardAddRoom = findViewById(R.id.cardAddRoom)
        etRoomName = findViewById(R.id.etRoomName)
        etRoomCapacity = findViewById(R.id.etRoomCapacity)
        etRoomLocation = findViewById(R.id.etRoomLocation)
        btnSubmitRoom = findViewById(R.id.btnSubmitRoom)
        rvRooms = findViewById(R.id.rvRooms)
        btnBack = findViewById(R.id.btnBackToCalendar)

        rvEvents.layoutManager = LinearLayoutManager(this)
        rvRooms.layoutManager = LinearLayoutManager(this)

        if (role in listOf("admin", "secretary")) {
            cardAddRoom.visibility = View.VISIBLE
        } else {
            cardAddRoom.visibility = View.GONE
        }
    }

    private fun setupApi() {
        val retrofit = RetrofitClient.getInstance(this)
        api = retrofit.create(CalendarApi::class.java)
    }

    private fun setupListeners() {
        btnCheckConflicts.setOnClickListener {
            showConflictCheckDialog()
        }

        btnManageRooms.setOnClickListener {
            flipper.displayedChild = 1 // Switch to Room Management
            loadRooms()
        }

        btnBack.setOnClickListener {
            flipper.displayedChild = 0 // Back to Calendar
        }

        btnSubmitRoom.setOnClickListener {
            val name = etRoomName.text.toString().trim()
            val capStr = etRoomCapacity.text.toString().trim()
            val loc = etRoomLocation.text.toString().trim()

            if (name.isEmpty() || capStr.isEmpty() || loc.isEmpty()) {
                Toast.makeText(this, getString(R.string.cal_fill), Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }

            createRoomOnServer(name, capStr.toInt(), loc)
        }
    }

    private fun loadEvents() {
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val list = api.getCalendarEvents()
                withContext(Dispatchers.Main) {
                    if (list.isEmpty()) {
                        Toast.makeText(this@CalendarActivity, getString(R.string.cal_not_found), Toast.LENGTH_SHORT).show()
                    }
                    rvEvents.adapter = CalendarAdapter(list)
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@CalendarActivity, getString(R.string.cal_error), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun loadRooms() {
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val list = api.getRoomsList()
                withContext(Dispatchers.Main) {
                    rvRooms.adapter = RoomsAdapter(list)
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@CalendarActivity, getString(R.string.cal_room_error), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun createRoomOnServer(name: String, capacity: Int, location: String) {
        val req = RoomCreateRequest(name, capacity, location)
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                api.createRoom(req)
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@CalendarActivity, getString(R.string.cal_room_done), Toast.LENGTH_SHORT).show()
                    etRoomName.text = null
                    etRoomCapacity.text = null
                    etRoomLocation.text = null
                    loadRooms() // Reload
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@CalendarActivity, getString(R.string.cal_room_fail), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun showConflictCheckDialog() {
        val view = LayoutInflater.from(this).inflate(R.layout.activity_add_class, null)
        
        // Customize the layout fields for conflict checking dialog
        val etTitle = view.findViewById<TextInputEditText>(R.id.etClassTitle)
        val etTeacherPrice = view.findViewById<TextInputEditText>(R.id.etTeacherPrice)
        val acTeacher = view.findViewById<AutoCompleteTextView>(R.id.acTeacher)
        val acGrade = view.findViewById<AutoCompleteTextView>(R.id.acGrade)
        val acEduType = view.findViewById<AutoCompleteTextView>(R.id.acEduType)
        
        etTitle.visibility = View.GONE
        etTeacherPrice.visibility = View.GONE
        acGrade.visibility = View.GONE
        acEduType.visibility = View.GONE
        
        // Re-purpose elements for day/time input
        val acDay = acTeacher
        val etTime = etTeacherPrice
        
        acDay.visibility = View.VISIBLE
        etTime.visibility = View.VISIBLE
        
        // Setup spinner values
        val days = arrayOf("شنبه", "یکشنبه", "دوشنبه", "سه شنبه", "چهارشنبه", "پنجشنبه", "جمعه")
        acDay.setAdapter(ArrayAdapter(this, android.R.layout.simple_dropdown_item_1line, days))
        acDay.setText("شنبه", false)
        acDay.hint = getString(R.string.cal_day_hint)
        
        etTime.setText("16:00")
        etTime.hint = getString(R.string.cal_time_hint)
        etTime.inputType = android.text.InputType.TYPE_CLASS_DATETIME

        AlertDialog.Builder(this)
            .setTitle(getString(R.string.cal_conflict_title))
            .setView(view)
            .setPositiveButton(getString(R.string.cal_conflict_check)) { _, _ ->
                val day = acDay.text.toString().trim()
                val time = etTime.text.toString().trim()
                
                checkConflictsOnServer(day, time)
            }
            .setNegativeButton(getString(R.string.common_cancel), null)
            .show()
    }

    private fun checkConflictsOnServer(day: String, time: String) {
        val req = ConflictCheckRequest(
            teacher_id = 1, // Simulated mock values for verification
            room_id = 1,
            days_of_week = day,
            class_time = time
        )
        // FIX: Bug 19 - cancel screen work when this Activity is destroyed.
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val res = api.checkConflicts(req)
                withContext(Dispatchers.Main) {
                    val alertBuilder = AlertDialog.Builder(this@CalendarActivity)
                    if (res.has_conflict) {
                        alertBuilder.setTitle(getString(R.string.cal_conflict_found))
                        alertBuilder.setMessage(res.details.joinToString("\n\n"))
                        alertBuilder.setIcon(android.R.drawable.ic_dialog_alert)
                    } else {
                        alertBuilder.setTitle(getString(R.string.cal_conflict_free))
                        alertBuilder.setMessage(res.message)
                        alertBuilder.setIcon(android.R.drawable.checkbox_on_background)
                    }
                    alertBuilder.setPositiveButton(getString(R.string.common_ok), null).show()
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation is not a network/UI error.
                if (e is kotlinx.coroutines.CancellationException) throw e;
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@CalendarActivity, getString(R.string.cal_conflict_error), Toast.LENGTH_SHORT).show()
                }
            }
        }
    }
}

class CalendarAdapter(
    private val list: List<CalendarEventItem>
) : RecyclerView.Adapter<CalendarAdapter.VH>() {

    class VH(v: View) : RecyclerView.ViewHolder(v) {
        val title: TextView = v.findViewById(R.id.tvEventTitle)
        val type: TextView = v.findViewById(R.id.tvEventType)
        val detail: TextView = v.findViewById(R.id.tvEventDetail)
        val schedule: TextView = v.findViewById(R.id.tvEventSchedule)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val v = LayoutInflater.from(parent.context).inflate(R.layout.item_calendar_event, parent, false)
        return VH(v)
    }

    override fun onBindViewHolder(holder: VH, position: Int) {
        val item = list[position]
        holder.title.text = item.title
        holder.detail.text = item.detail
        holder.schedule.text = holder.itemView.context.getString(R.string.cal_time_row, item.schedule)

        val typeVal = item.type.lowercase()
        holder.type.text = when (typeVal) {
            "class" -> holder.itemView.context.getString(R.string.cal_type_class)
            "exam" -> holder.itemView.context.getString(R.string.cal_type_exam)
            "homework deadline" -> holder.itemView.context.getString(R.string.cal_type_hw)
            "payment due" -> holder.itemView.context.getString(R.string.cal_type_pay)
            else -> item.type
        }
    }

    override fun getItemCount() = list.size
}

class RoomsAdapter(
    private val list: List<RoomItem>
) : RecyclerView.Adapter<RoomsAdapter.VH>() {

    class VH(v: View) : RecyclerView.ViewHolder(v) {
        val name: TextView = v.findViewById(R.id.tvRoomName)
        val capacity: TextView = v.findViewById(R.id.tvRoomCapacity)
        val location: TextView = v.findViewById(R.id.tvRoomLocation)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val v = LayoutInflater.from(parent.context).inflate(R.layout.item_room, parent, false)
        return VH(v)
    }

    override fun onBindViewHolder(holder: VH, position: Int) {
        val item = list[position]
        holder.name.text = holder.itemView.context.getString(R.string.cal_room_row, item.name)
        holder.capacity.text = holder.itemView.context.getString(R.string.cal_cap_row, item.capacity)
        holder.location.text = holder.itemView.context.getString(R.string.cal_loc_row, item.location)
    }

    override fun getItemCount() = list.size
}
