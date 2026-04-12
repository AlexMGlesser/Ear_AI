package com.earai.mobile

import android.content.Context

object DiagnosticsStore {
    private const val PREF = "ear_ai_diagnostics"

    fun save(
        context: Context,
        engine: String,
        listening: Boolean,
        activeVoice: String,
        wakeHits: Int,
        queriesSent: Int,
        lastTranscript: String,
        lastConfidence: Float,
        lastError: String,
        lastRttMs: Long
    ) {
        context.getSharedPreferences(PREF, Context.MODE_PRIVATE).edit()
            .putString("engine", engine)
            .putBoolean("listening", listening)
            .putString("active_voice", activeVoice)
            .putInt("wake_hits", wakeHits)
            .putInt("queries_sent", queriesSent)
            .putString("last_transcript", lastTranscript)
            .putFloat("last_confidence", lastConfidence)
            .putString("last_error", lastError)
            .putLong("last_rtt_ms", lastRttMs)
            .apply()
    }

    fun load(context: Context): BundleData {
        val prefs = context.getSharedPreferences(PREF, Context.MODE_PRIVATE)
        return BundleData(
            engine = prefs.getString("engine", "NONE").orEmpty(),
            listening = prefs.getBoolean("listening", false),
            activeVoice = prefs.getString("active_voice", "-").orEmpty(),
            wakeHits = prefs.getInt("wake_hits", 0),
            queriesSent = prefs.getInt("queries_sent", 0),
            lastTranscript = prefs.getString("last_transcript", "").orEmpty(),
            lastConfidence = prefs.getFloat("last_confidence", -1.0f),
            lastError = prefs.getString("last_error", "").orEmpty(),
            lastRttMs = prefs.getLong("last_rtt_ms", -1L)
        )
    }

    data class BundleData(
        val engine: String,
        val listening: Boolean,
        val activeVoice: String,
        val wakeHits: Int,
        val queriesSent: Int,
        val lastTranscript: String,
        val lastConfidence: Float,
        val lastError: String,
        val lastRttMs: Long
    )
}
