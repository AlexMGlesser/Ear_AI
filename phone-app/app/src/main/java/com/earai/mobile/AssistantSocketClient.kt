package com.earai.mobile

import android.os.Handler
import android.os.Looper
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import org.json.JSONObject
import java.time.Instant
import java.util.UUID
import java.util.concurrent.TimeUnit
import kotlin.math.min

class AssistantSocketClient(
    private val host: String,
    private val port: Int,
    private val onAssistantReply: (String) -> Unit,
    private val onError: (String) -> Unit
) {
    private val sessionId: String = UUID.randomUUID().toString()
    private val client = OkHttpClient.Builder()
        .retryOnConnectionFailure(true)
        .pingInterval(20, TimeUnit.SECONDS)
        .build()
    private val mainHandler = Handler(Looper.getMainLooper())

    private var webSocket: WebSocket? = null
    private var isConnected: Boolean = false
    private var reconnectAttempts: Int = 0
    private var isClosedByClient: Boolean = false
    private var pendingPayload: String? = null

    fun connect() {
        isClosedByClient = false
        openSocket()
    }

    private fun openSocket() {
        val request = Request.Builder()
            .url("ws://$host:$port/ws/assistant")
            .build()

        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                isConnected = true
                reconnectAttempts = 0
                val queued = pendingPayload
                if (!queued.isNullOrBlank()) {
                    if (webSocket.send(queued)) {
                        pendingPayload = null
                    }
                }
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                try {
                    val json = JSONObject(text)
                    val type = json.optString("type")
                    if (type == "assistant_response") {
                        onAssistantReply(json.optString("text", ""))
                    } else if (type == "error") {
                        onError(json.optString("message", "Unknown server error"))
                    }
                } catch (ex: Exception) {
                    onError("Invalid response: ${ex.message}")
                }
            }

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                isConnected = false
                webSocket.close(code, reason)
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                isConnected = false
                if (!isClosedByClient) {
                    scheduleReconnect("Socket closed ($code): $reason")
                }
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                isConnected = false
                onError("Socket failure: ${t.message ?: "unknown"}")
                if (!isClosedByClient) {
                    scheduleReconnect("Socket reconnecting")
                }
            }
        })
    }

    fun sendUserUtterance(text: String) {
        val payload = JSONObject()
            .put("type", "user_utterance")
            .put("session_id", sessionId)
            .put("text", text)
            .put("timestamp", Instant.now().toString())
        val payloadText = payload.toString()
        pendingPayload = payloadText

        val sent = sendPayload(payloadText)
        if (sent) {
            pendingPayload = null
            return
        }

        scheduleReconnect("Socket unavailable, reconnecting")
    }

    private fun sendPayload(payload: String): Boolean {
        val socket = webSocket ?: return false
        if (!isConnected) return false
        return socket.send(payload)
    }

    private fun scheduleReconnect(reason: String) {
        onError(reason)
        reconnectAttempts += 1
        val delayMs = min(1_000L * reconnectAttempts, 5_000L)
        mainHandler.removeCallbacks(reconnectRunnable)
        mainHandler.postDelayed(reconnectRunnable, delayMs)
    }

    fun close() {
        isClosedByClient = true
        mainHandler.removeCallbacks(reconnectRunnable)
        webSocket?.close(1000, "client closing")
        client.dispatcher.executorService.shutdown()
    }

    private val reconnectRunnable = Runnable {
        if (!isClosedByClient) {
            openSocket()
        }
    }
}
