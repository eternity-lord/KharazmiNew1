package com.example.kharazmiadmin

import android.graphics.Color
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import androidx.recyclerview.widget.RecyclerView
import com.google.android.material.card.MaterialCardView

class TimelineAdapter(
    private var items: List<TimelineEvent>
) : RecyclerView.Adapter<TimelineAdapter.VH>() {

    inner class VH(view: View) : RecyclerView.ViewHolder(view) {
        val tvIcon: TextView = view.findViewById(R.id.tvTimelineIcon)
        val cardIcon: MaterialCardView = view.findViewById(R.id.cardTimelineIcon)
        val tvTitle: TextView = view.findViewById(R.id.tvTimelineTitle)
        val tvSubtitle: TextView = view.findViewById(R.id.tvTimelineSubtitle)
        val tvDate: TextView = view.findViewById(R.id.tvTimelineDate)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val v = LayoutInflater.from(parent.context).inflate(R.layout.item_timeline_event, parent, false)
        return VH(v)
    }

    override fun getItemCount(): Int = items.size

    override fun onBindViewHolder(holder: VH, position: Int) {
        val ev = items[position]
        holder.tvTitle.text = ev.title
        holder.tvSubtitle.text = ev.subtitle
        holder.tvDate.text = ev.timestamp

        // Icon fills and title text use separate semantic tokens: bright status text remains
        // readable on the dark/light icon fills in both palettes.
        val (iconColor, titleColor) = try {
            val serverColor = Color.parseColor(ev.colorHex)
            serverColor to serverColor
        } catch (_: Exception) {
            when (ev.type) {
                "payment" -> UiColors.resolve(holder.itemView.context, R.color.status_success_deep) to
                    UiColors.resolve(holder.itemView.context, R.color.status_success)
                "absence" -> UiColors.resolve(holder.itemView.context, R.color.ds_danger_deep) to
                    UiColors.resolve(holder.itemView.context, R.color.status_danger)
                "grade" -> UiColors.resolve(holder.itemView.context, R.color.status_info_deep) to
                    UiColors.resolve(holder.itemView.context, R.color.status_info)
                "installment" -> UiColors.resolve(holder.itemView.context, R.color.status_warning_deep) to
                    UiColors.resolve(holder.itemView.context, R.color.status_warning)
                else -> UiColors.resolve(holder.itemView.context, R.color.status_neutral_deep) to
                    UiColors.resolve(holder.itemView.context, R.color.text_secondary)
            }
        }
        holder.cardIcon.setCardBackgroundColor(iconColor)

        val iconText = when (ev.type) {
            "payment" -> "💰"
            "absence" -> "❌"
            "grade" -> "📝"
            "installment" -> if (ev.colorHex == "#4CAF50") "✅" else if (ev.colorHex == "#F44336") "🔴" else "⏳"
            else -> when (ev.iconName) {
                "ic_payment" -> "💰"
                "ic_absent" -> "❌"
                "ic_grade" -> "📝"
                "ic_installment" -> "💳"
                "ic_paid" -> "✅"
                "ic_overdue" -> "🔴"
                else -> "📌"
            }
        }
        holder.tvIcon.text = iconText
        holder.tvTitle.setTextColor(titleColor)
    }

    fun update(newList: List<TimelineEvent>) {
        items = newList
        notifyDataSetChanged()
    }
}
