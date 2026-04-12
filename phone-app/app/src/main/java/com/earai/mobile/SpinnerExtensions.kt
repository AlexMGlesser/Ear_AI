package com.earai.mobile

import android.view.View
import android.widget.AdapterView
import android.widget.Spinner

fun Spinner.onItemSelected(onSelected: (AdapterView<*>, View?, Int, Long) -> Unit) {
    onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
        override fun onItemSelected(parent: AdapterView<*>, view: View?, position: Int, id: Long) {
            onSelected(parent, view, position, id)
        }

        override fun onNothingSelected(parent: AdapterView<*>) {
            // No-op.
        }
    }
}
