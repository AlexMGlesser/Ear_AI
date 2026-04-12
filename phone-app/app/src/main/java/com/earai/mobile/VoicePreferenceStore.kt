package com.earai.mobile

import android.content.Context

object VoicePreferenceStore {
    private const val PREF = "ear_ai_voice"
    private const val KEY_VOICE_NAME = "selected_voice_name"

    fun saveSelectedVoiceName(context: Context, voiceName: String?) {
        context.getSharedPreferences(PREF, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY_VOICE_NAME, voiceName.orEmpty())
            .apply()
    }

    fun loadSelectedVoiceName(context: Context): String {
        return context.getSharedPreferences(PREF, Context.MODE_PRIVATE)
            .getString(KEY_VOICE_NAME, "")
            .orEmpty()
    }
}
