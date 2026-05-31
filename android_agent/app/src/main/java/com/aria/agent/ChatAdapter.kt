package com.aria.agent

import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.RelativeLayout
import android.widget.TextView
import androidx.core.content.ContextCompat
import androidx.recyclerview.widget.RecyclerView

data class ChatMessage(
    val id: String,
    val isUser: Boolean,
    var text: String,
    var isStreaming: Boolean = false
)

class ChatAdapter : RecyclerView.Adapter<ChatAdapter.ChatViewHolder>() {

    private val messages = mutableListOf<ChatMessage>()

    fun addUserMessage(text: String) {
        messages.add(ChatMessage(System.currentTimeMillis().toString(), true, text))
        notifyItemInserted(messages.size - 1)
    }

    fun addOrUpdateAriaChunk(chunk: String) {
        if (chunk == "<DONE>") {
            if (messages.isNotEmpty() && messages.last().isStreaming) {
                messages.last().isStreaming = false
                notifyItemChanged(messages.size - 1)
            }
            return
        }

        if (messages.isEmpty() || messages.last().isUser || !messages.last().isStreaming) {
            // Create new ARIA message
            messages.add(ChatMessage(System.currentTimeMillis().toString(), false, chunk, true))
            notifyItemInserted(messages.size - 1)
        } else {
            // Append to existing streaming message
            val last = messages.last()
            last.text += chunk
            notifyItemChanged(messages.size - 1)
        }
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ChatViewHolder {
        val view = LayoutInflater.from(parent.context).inflate(R.layout.item_chat, parent, false)
        return ChatViewHolder(view)
    }

    override fun onBindViewHolder(holder: ChatViewHolder, position: Int) {
        val message = messages[position]
        holder.bind(message)
    }

    override fun getItemCount(): Int = messages.size

    class ChatViewHolder(itemView: View) : RecyclerView.ViewHolder(itemView) {
        private val tvMessage: TextView = itemView.findViewById(R.id.tvMessage)

        fun bind(message: ChatMessage) {
            tvMessage.text = message.text
            
            // Apply styling based on sender
            val context = itemView.context
            val lp = tvMessage.layoutParams as RelativeLayout.LayoutParams
            val density = context.resources.displayMetrics.density
            val margin80 = (80 * density).toInt()

            if (message.isUser) {
                tvMessage.setBackgroundResource(R.drawable.bg_chat_user)
                tvMessage.setTextColor(ContextCompat.getColor(context, android.R.color.white))
                lp.addRule(RelativeLayout.ALIGN_PARENT_END)
                lp.removeRule(RelativeLayout.ALIGN_PARENT_START)
                lp.marginStart = margin80
                lp.marginEnd = 0
            } else {
                tvMessage.setBackgroundResource(R.drawable.bg_chat_aria)
                tvMessage.setTextColor(ContextCompat.getColor(context, R.color.colorAccent)) // Cyan text for ARIA
                lp.addRule(RelativeLayout.ALIGN_PARENT_START)
                lp.removeRule(RelativeLayout.ALIGN_PARENT_END)
                lp.marginStart = 0
                lp.marginEnd = margin80
            }
            tvMessage.layoutParams = lp
            itemView.requestLayout()
        }
    }
}
