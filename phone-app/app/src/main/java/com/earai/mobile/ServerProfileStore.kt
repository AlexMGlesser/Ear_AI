package com.earai.mobile

import android.content.Context

data class ServerProfile(
    val label: String,
    val host: String,
    val port: Int
)

object ServerProfileStore {
    private const val PREF_NAME = "ear_ai_profiles"
    private const val KEY_HOST = "last_host"
    private const val KEY_PORT = "last_port"

    fun defaultProfiles(): List<ServerProfile> = listOf(
        ServerProfile("Home Desktop", "192.168.1.100", 8765),
        ServerProfile("Laptop", "192.168.1.50", 8765),
        ServerProfile("Custom", "", 8765)
    )

    fun saveLastServer(context: Context, host: String, port: Int) {
        val prefs = context.getSharedPreferences(PREF_NAME, Context.MODE_PRIVATE)
        prefs.edit().putString(KEY_HOST, host).putInt(KEY_PORT, port).apply()
    }

    fun loadLastServer(context: Context): ServerProfile? {
        val prefs = context.getSharedPreferences(PREF_NAME, Context.MODE_PRIVATE)
        val host = prefs.getString(KEY_HOST, null) ?: return null
        val port = prefs.getInt(KEY_PORT, 8765)
        return ServerProfile("Last Used", host, port)
    }
}
