package com.example.kharazmiadmin

import android.view.Gravity
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.LinearLayout
import android.widget.TextView
import androidx.core.content.ContextCompat
import androidx.recyclerview.widget.RecyclerView
import com.google.android.material.card.MaterialCardView
import com.google.android.material.color.MaterialColors
import com.google.gson.annotations.SerializedName

/** Read-only item returned by the student/teacher communication history endpoints. */
data class CommunicationHistoryItem(
    @SerializedName("source_id") val sourceId: Int,
    val type: String,
    @SerializedName("type_label") val typeLabel: String,
    val summary: String,
    val date: String,
    val sender: String,
    val recipient: String,
    val direction: String,
    @SerializedName("conversation_id") val conversationId: Int? = null
)

class CommunicationHistoryAdapter(
    private val items: List<CommunicationHistoryItem>
) : RecyclerView.Adapter<CommunicationHistoryAdapter.ViewHolder>() {

    class ViewHolder(view: View) : RecyclerView.ViewHolder(view) {
        val card: MaterialCardView = view.findViewById(R.id.cardCommunicationBubble)
        val type: TextView = view.findViewById(R.id.tvCommunicationType)
        val date: TextView = view.findViewById(R.id.tvCommunicationDate)
        val parties: TextView = view.findViewById(R.id.tvCommunicationParties)
        val summary: TextView = view.findViewById(R.id.tvCommunicationSummary)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder {
        val view = LayoutInflater.from(parent.context)
            .inflate(R.layout.item_communication_history, parent, false)
        return ViewHolder(view)
    }

    override fun onBindViewHolder(holder: ViewHolder, position: Int) {
        val item = items[position]
        val isSms = item.type == "sms"
        holder.type.text = if (isSms) holder.itemView.context.getString(R.string.commhist_type_sms, item.typeLabel) else holder.itemView.context.getString(R.string.commhist_type_chat, item.typeLabel)
        holder.date.text = item.date
        holder.parties.text = holder.itemView.context.getString(R.string.commhist_parties, item.sender, item.recipient)
        holder.summary.text = item.summary

        val params = holder.card.layoutParams as LinearLayout.LayoutParams
        if (item.direction == "outgoing") {
            params.gravity = Gravity.LEFT
            holder.card.setCardBackgroundColor(
                ContextCompat.getColor(holder.itemView.context, R.color.gaj_success_light)
            )
        } else {
            params.gravity = Gravity.RIGHT
            holder.card.setCardBackgroundColor(
                MaterialColors.getColor(
                    holder.card,
                    com.google.android.material.R.attr.colorSurface
                )
            )
        }
        holder.card.layoutParams = params
        holder.card.strokeColor = if (isSms) {
            ContextCompat.getColor(holder.itemView.context, R.color.gaj_info)
        } else {
            MaterialColors.getColor(
                holder.card,
                com.google.android.material.R.attr.colorPrimary
            )
        }
    }

    override fun getItemCount(): Int = items.size
}
