package com.earai.mobile

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.PowerManager
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.speech.tts.Voice
import androidx.core.app.NotificationCompat
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import java.util.Locale

class VoiceAssistantService : Service(), TextToSpeech.OnInitListener {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    private var wakeLock: PowerManager.WakeLock? = null
    private val mainHandler = Handler(Looper.getMainLooper())

    private var recognizer: SpeechRecognizer? = null
    private var tts: TextToSpeech? = null
    private var socketClient: AssistantSocketClient? = null
    private var voskOfflineEngine: VoskOfflineEngine? = null
    private lateinit var audioRouteController: AudioRouteController
    private val wakeFlowController = WakeFlowController("dante")

    private var isRecognizerStarted = false
    private var isTtsSpeaking = false
    private var isTtsReady = false
    private var recognitionErrorStreak = 0
    private var activeEngine: Engine = Engine.NONE
    private var allowOnlineFallback: Boolean = false
    private var selectedVoiceName: String = ""
    private var wakeHitCount: Int = 0
    private var querySentCount: Int = 0
    private var lastTranscript: String = ""
    private var lastConfidence: Float = -1.0f
    private var lastError: String = ""
    private var activeVoiceLabel: String = "auto"
    private var pendingSendAtMs: Long = 0L
    private var lastRttMs: Long = -1L

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
        tts = TextToSpeech(this, this)
        audioRouteController = AudioRouteController(this)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_START -> {
                val host = intent.getStringExtra(EXTRA_HOST).orEmpty()
                val port = intent.getIntExtra(EXTRA_PORT, 8765)
                allowOnlineFallback = intent.getBooleanExtra(EXTRA_ALLOW_ONLINE_FALLBACK, false)
                selectedVoiceName = intent.getStringExtra(EXTRA_VOICE_NAME).orEmpty()
                if (isTtsReady) {
                    configurePreferredVoice()
                }
                startForeground(NOTIFICATION_ID, buildNotification("Listening for 'Dante'"))
                acquireWakeLock()
                audioRouteController.startVoiceSession()
                connectSocket(host, port)
                startListeningPipeline()
            }

            ACTION_STOP -> stopSelfSafely()
        }
        return START_STICKY
    }

    private fun connectSocket(host: String, port: Int) {
        socketClient?.close()
        socketClient = AssistantSocketClient(
            host = host,
            port = port,
            onAssistantReply = { text ->
                speak(text)
                updateNotification("Assistant replied")
                if (pendingSendAtMs > 0L) {
                    lastRttMs = System.currentTimeMillis() - pendingSendAtMs
                    pendingSendAtMs = 0L
                }
                publishDiagnostics()
            },
            onError = { message ->
                updateNotification(message)
                lastError = message
                publishDiagnostics()
            }
        )
        socketClient?.connect()
    }

    private fun startListeningPipeline() {
        if (startVoskOfflineEngine()) {
            activeEngine = Engine.VOSK
            updateNotification("Offline listening active")
            publishDiagnostics()
            return
        }

        if (allowOnlineFallback) {
            activeEngine = Engine.SPEECH_RECOGNIZER
            updateNotification("Fallback listening active")
            publishDiagnostics()
            startSpeechRecognition()
            return
        }

        activeEngine = Engine.NONE
        updateNotification("Offline model missing. Add model to enable listening")
        lastError = "Offline model missing and fallback disabled"
        publishDiagnostics()
    }

    private fun startVoskOfflineEngine(): Boolean {
        voskOfflineEngine?.stop()
        voskOfflineEngine = VoskOfflineEngine(
            context = this,
            onWakePartial = { partial ->
                if (wakeFlowController.currentState() == WakeFlowController.State.WAITING_WAKE &&
                    wakeFlowController.detectWakePhrase(partial)
                ) {
                    wakeHitCount += 1
                    updateNotification("Wake phrase detected, awaiting command")
                    scheduleQueryTimeout()
                    publishDiagnostics()
                }
            },
            onFinalTranscript = { transcript, confidence ->
                lastTranscript = transcript
                lastConfidence = confidence ?: -1.0f
                processTranscript(transcript)
                publishDiagnostics()
            },
            onError = { error ->
                updateNotification(error)
                lastError = error
                publishDiagnostics()
            }
        )
        return voskOfflineEngine?.start() == true
    }

    private fun startSpeechRecognition() {
        if (!SpeechRecognizer.isRecognitionAvailable(this)) {
            updateNotification("Speech recognizer unavailable")
            return
        }

        recognizer?.destroy()
        recognizer = SpeechRecognizer.createSpeechRecognizer(this)
        recognizer?.setRecognitionListener(object : RecognitionListener {
            override fun onReadyForSpeech(params: Bundle?) = Unit
            override fun onBeginningOfSpeech() = Unit
            override fun onRmsChanged(rmsdB: Float) = Unit
            override fun onBufferReceived(buffer: ByteArray?) = Unit
            override fun onEndOfSpeech() = Unit

            override fun onError(error: Int) {
                isRecognizerStarted = false
                recognitionErrorStreak = (recognitionErrorStreak + 1).coerceAtMost(5)
                val backoffMs = 350L * recognitionErrorStreak
                lastError = "Speech recognizer error code $error"
                publishDiagnostics()
                scheduleRestartListening(backoffMs)
            }

            override fun onResults(results: Bundle?) {
                isRecognizerStarted = false
                recognitionErrorStreak = 0
                val candidates = results
                    ?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                    ?.map { it.trim() }
                    ?.filter { it.isNotBlank() }
                    .orEmpty()
                val text = chooseBestTranscript(candidates)
                val confidence = results
                    ?.getFloatArray(SpeechRecognizer.CONFIDENCE_SCORES)
                    ?.maxOrNull()
                    ?: -1.0f
                lastTranscript = text
                lastConfidence = confidence

                if (text.isNotBlank()) {
                    processTranscript(text)
                }
                publishDiagnostics()
                scheduleRestartListening(300L)
            }

            override fun onPartialResults(partialResults: Bundle?) {
                val candidates = partialResults
                    ?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                    ?.map { it.trim() }
                    ?.filter { it.isNotBlank() }
                    .orEmpty()
                val text = chooseBestTranscript(candidates)
                if (wakeFlowController.detectWakePhrase(text)) {
                    wakeHitCount += 1
                    updateNotification("Wake phrase detected, awaiting command")
                    scheduleQueryTimeout()
                    publishDiagnostics()
                }
            }

            override fun onEvent(eventType: Int, params: Bundle?) = Unit
        })

        restartListening()
    }

    private fun processTranscript(text: String) {
        if (wakeFlowController.currentState() == WakeFlowController.State.WAITING_WAKE) {
            if (wakeFlowController.detectWakePhrase(text)) {
                wakeHitCount += 1
                updateNotification("Wake phrase detected, awaiting command")
                scheduleQueryTimeout()
                publishDiagnostics()
            }
            return
        }

        val cleaned = wakeFlowController.consumeUtterance(text)
        if (cleaned == null) {
            return
        }

        if (cleaned.isBlank()) {
            updateNotification("Awaiting command...")
            scheduleQueryTimeout()
            return
        }

        mainHandler.removeCallbacks(queryTimeoutRunnable)
        updateNotification("Sending query")
        pendingSendAtMs = System.currentTimeMillis()
        querySentCount += 1
        socketClient?.sendUserUtterance(cleaned)
        publishDiagnostics()
    }

    private fun chooseBestTranscript(candidates: List<String>): String {
        if (candidates.isEmpty()) return ""
        val waitingWake = wakeFlowController.currentState() == WakeFlowController.State.WAITING_WAKE

        if (waitingWake) {
            val wakeLike = candidates.firstOrNull { TranscriptNormalizer.containsWakeLikeToken(it) }
            if (!wakeLike.isNullOrBlank()) {
                return wakeLike
            }
        }

        return candidates.firstOrNull().orEmpty()
    }

    private fun restartListening() {
        if (activeEngine != Engine.SPEECH_RECOGNIZER) {
            return
        }
        if (isTtsSpeaking) {
            return
        }
        if (isRecognizerStarted) {
            return
        }
        recognizer?.cancel()
        recognizer?.startListening(recognizerIntent())
        isRecognizerStarted = true
    }

    private fun scheduleRestartListening(delayMs: Long) {
        mainHandler.removeCallbacks(restartListeningRunnable)
        mainHandler.postDelayed(restartListeningRunnable, delayMs)
    }

    private fun scheduleQueryTimeout() {
        mainHandler.removeCallbacks(queryTimeoutRunnable)
        mainHandler.postDelayed(queryTimeoutRunnable, QUERY_TIMEOUT_MS)
    }

    private fun recognizerIntent(): Intent {
        return Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault())
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
            putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, true)
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_MINIMUM_LENGTH_MILLIS, 5_000)
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS, 2_000)
            putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 2_600)
        }
    }

    private fun speak(text: String) {
        if (text.isBlank()) return

        isTtsSpeaking = true
        recognizer?.cancel()
        isRecognizerStarted = false
        tts?.speak(text, TextToSpeech.QUEUE_FLUSH, null, "assistant_reply")
    }

    private fun buildNotification(content: String): Notification {
        val stopIntent = Intent(this, VoiceAssistantService::class.java).apply {
            action = ACTION_STOP
        }
        val stopPendingIntent = PendingIntent.getService(
            this,
            100,
            stopIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Ear AI running")
            .setContentText(content)
            .setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .setOngoing(true)
            .addAction(android.R.drawable.ic_media_pause, "Stop", stopPendingIntent)
            .build()
    }

    private fun updateNotification(content: String) {
        val manager = getSystemService(NotificationManager::class.java)
        manager.notify(NOTIFICATION_ID, buildNotification(content))
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val channel = NotificationChannel(
            CHANNEL_ID,
            "Ear AI Service",
            NotificationManager.IMPORTANCE_LOW
        )
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(channel)
    }

    private fun acquireWakeLock() {
        val pm = getSystemService(POWER_SERVICE) as PowerManager
        wakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "EarAI::MicLock").apply {
            setReferenceCounted(false)
            acquire()
        }
    }

    private fun releaseWakeLock() {
        wakeLock?.takeIf { it.isHeld }?.release()
        wakeLock = null
    }

    private fun stopSelfSafely() {
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            isTtsReady = true
            configurePreferredVoice()
            tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                override fun onStart(utteranceId: String?) = Unit

                override fun onDone(utteranceId: String?) {
                    mainHandler.post {
                        isTtsSpeaking = false
                        scheduleRestartListening(250L)
                    }
                }

                @Deprecated("Deprecated in Java")
                override fun onError(utteranceId: String?) {
                    mainHandler.post {
                        isTtsSpeaking = false
                        scheduleRestartListening(250L)
                    }
                }
            })
        }
    }

    private fun configurePreferredVoice() {
        val engine = tts ?: return

        if (applyVoiceProfileIfSelected(engine)) {
            return
        }

        val selected = if (selectedVoiceName.isBlank()) {
            null
        } else {
            engine.voices?.firstOrNull { it.name == selectedVoiceName }
        }

        val preferred = selected ?: selectBestVoice(engine)
        if (preferred != null) {
            engine.voice = preferred
            engine.language = preferred.locale
            activeVoiceLabel = "${preferred.locale.toLanguageTag()} ${preferred.name}"
        } else {
            engine.language = Locale.UK
            activeVoiceLabel = "auto-locale-uk"
        }

        // Slightly lower pitch/rate to sound less sharp and more natural in earbuds.
        engine.setPitch(0.9f)
        engine.setSpeechRate(0.95f)
        publishDiagnostics()
    }

    private fun applyVoiceProfileIfSelected(engine: TextToSpeech): Boolean {
        return when (selectedVoiceName) {
            VOICE_PROFILE_UK_MALE -> {
                val chosen = engine.voices
                    ?.filter { it.locale.language.equals("en", ignoreCase = true) }
                    ?.filter { it.locale.country.equals("GB", ignoreCase = true) }
                    ?.maxByOrNull { voiceScore(it) }

                if (chosen != null) {
                    engine.voice = chosen
                    engine.language = chosen.locale
                    activeVoiceLabel = "uk-male:${chosen.name}"
                } else {
                    engine.language = Locale.UK
                    activeVoiceLabel = "uk-male:profile-only"
                }

                engine.setPitch(0.72f)
                engine.setSpeechRate(0.9f)
                publishDiagnostics()
                true
            }

            VOICE_PROFILE_UK_FEMALE -> {
                val chosen = engine.voices
                    ?.filter { it.locale.language.equals("en", ignoreCase = true) }
                    ?.filter { it.locale.country.equals("GB", ignoreCase = true) }
                    ?.minByOrNull { voiceScore(it) }

                if (chosen != null) {
                    engine.voice = chosen
                    engine.language = chosen.locale
                    activeVoiceLabel = "uk-female:${chosen.name}"
                } else {
                    engine.language = Locale.UK
                    activeVoiceLabel = "uk-female:profile-only"
                }

                engine.setPitch(1.08f)
                engine.setSpeechRate(1.0f)
                publishDiagnostics()
                true
            }

            else -> false
        }
    }

    private fun selectBestVoice(engine: TextToSpeech): Voice? {
        val voices = engine.voices ?: return null

        return voices
            .filter { it.locale.language.equals("en", ignoreCase = true) }
            .maxByOrNull { voiceScore(it) }
    }

    private fun voiceScore(voice: Voice): Int {
        val name = voice.name.lowercase(Locale.ROOT)
        val locale = voice.locale
        val features = voice.features?.map { it.lowercase(Locale.ROOT) } ?: emptyList()

        var score = 0

        if (locale.country.equals("GB", ignoreCase = true)) score += 100
        if (locale.country.equals("US", ignoreCase = true)) score += 40

        if ("male" in name) score += 25
        if (name.contains("-m") || name.contains("_m")) score += 10

        if (features.any { it.contains("network") }) score -= 5
        if (name.contains("female") || name.contains("-f") || name.contains("_f")) score -= 10

        return score
    }

    override fun onDestroy() {
        super.onDestroy()
        mainHandler.removeCallbacksAndMessages(null)
        recognizer?.destroy()
        recognizer = null
        tts?.stop()
        tts?.shutdown()
        tts = null
        isTtsReady = false
        socketClient?.close()
        socketClient = null
        voskOfflineEngine?.stop()
        voskOfflineEngine = null
        activeEngine = Engine.NONE
        audioRouteController.stopVoiceSession()
        releaseWakeLock()
        scope.cancel()
        publishDiagnostics()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    companion object {
        const val ACTION_START = "com.earai.mobile.action.START"
        const val ACTION_STOP = "com.earai.mobile.action.STOP"
        const val ACTION_STATUS = "com.earai.mobile.action.STATUS"
        const val EXTRA_HOST = "extra_host"
        const val EXTRA_PORT = "extra_port"
        const val EXTRA_ALLOW_ONLINE_FALLBACK = "extra_allow_online_fallback"
        const val EXTRA_VOICE_NAME = "extra_voice_name"
        const val VOICE_PROFILE_UK_MALE = "profile:uk_male"
        const val VOICE_PROFILE_UK_FEMALE = "profile:uk_female"

        private const val CHANNEL_ID = "ear_ai_foreground"
        private const val NOTIFICATION_ID = 101
        private const val QUERY_TIMEOUT_MS = 11_000L
    }

    private val restartListeningRunnable = Runnable { restartListening() }

    private val queryTimeoutRunnable = Runnable {
        wakeFlowController.resetToWake()
        updateNotification("Wake timed out, listening for 'Dante'")
        publishDiagnostics()
    }

    private fun publishDiagnostics() {
        val activeAudioDevice = audioRouteController.getActiveAudioDevice()
        
        DiagnosticsStore.save(
            context = this,
            engine = activeEngine.name,
            listening = activeEngine != Engine.NONE,
            activeVoice = activeVoiceLabel,
            wakeHits = wakeHitCount,
            queriesSent = querySentCount,
            lastTranscript = lastTranscript,
            lastConfidence = lastConfidence,
            lastError = lastError,
            lastRttMs = lastRttMs,
            audioDevice = activeAudioDevice
        )

        val intent = Intent(ACTION_STATUS).apply {
            putExtra("engine", activeEngine.name)
            putExtra("wake_hits", wakeHitCount)
            putExtra("queries_sent", querySentCount)
            putExtra("last_transcript", lastTranscript)
            putExtra("last_confidence", lastConfidence)
            putExtra("last_error", lastError)
            putExtra("last_rtt_ms", lastRttMs)
            putExtra("active_voice", activeVoiceLabel)
            putExtra("listening", activeEngine != Engine.NONE)
            putExtra("audio_device", activeAudioDevice)
        }
        sendBroadcast(intent)
    }

    private enum class Engine {
        NONE,
        VOSK,
        SPEECH_RECOGNIZER
    }
}
