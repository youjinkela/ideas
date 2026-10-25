package com.ideaecho.app

import android.content.Context
import android.view.MotionEvent
import android.view.View
import android.view.ViewConfiguration
import android.view.ViewGroup
import android.widget.FrameLayout
import android.widget.HorizontalScrollView
import androidx.recyclerview.widget.RecyclerView
import kotlin.math.abs

/** Keep each form alive while the pager attaches and detaches its page containers. */
internal class SwipePageAdapter(private val pages: List<View>): RecyclerView.Adapter<SwipePageAdapter.Holder>() {
    class Holder(val container: FrameLayout): RecyclerView.ViewHolder(container)
    override fun getItemCount()=pages.size
    override fun onCreateViewHolder(parent: ViewGroup,viewType: Int)=Holder(FrameLayout(parent.context).apply {
        layoutParams=RecyclerView.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,ViewGroup.LayoutParams.MATCH_PARENT)
    })
    override fun onBindViewHolder(holder: Holder,position: Int) {
        val page=pages[position]
        (page.parent as? ViewGroup)?.removeView(page)
        holder.container.removeAllViews()
        holder.container.addView(page,FrameLayout.LayoutParams(-1,-1))
    }
    override fun onViewRecycled(holder: Holder) { holder.container.removeAllViews() }
}

/** Image-strip gestures scroll the images first; page swipes resume at the strip's edge. */
internal class HistoryImageScroller(context: Context): HorizontalScrollView(context) {
    private val slop=ViewConfiguration.get(context).scaledTouchSlop
    private var startX=0f
    private var startY=0f
    override fun dispatchTouchEvent(event: MotionEvent): Boolean {
        when(event.actionMasked) {
            MotionEvent.ACTION_DOWN->{startX=event.x;startY=event.y;parent?.requestDisallowInterceptTouchEvent(true)}
            MotionEvent.ACTION_MOVE->{
                val dx=event.x-startX;val dy=event.y-startY
                if(abs(dx)>slop || abs(dy)>slop)parent?.requestDisallowInterceptTouchEvent(abs(dx)>abs(dy) && canScrollHorizontally(if(dx<0)1 else -1))
            }
            MotionEvent.ACTION_UP,MotionEvent.ACTION_CANCEL->parent?.requestDisallowInterceptTouchEvent(false)
        }
        return super.dispatchTouchEvent(event)
    }
}
