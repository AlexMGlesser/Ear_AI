package com.earai.mobile

import android.Manifest
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.speech.tts.TextToSpeech
import android.speech.tts.Voice
import android.widget.ArrayAdapter
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat.RECEIVER_NOT_EXPORTED
import androidx.core.content.ContextCompat
import com.earai.mobile.databinding.ActivityMainBinding

class MainActivity : AppCompatActivity() {
    private lateinit var binding: ActivityMainBinding
    private val profiles = mutableListOf<ServerProfile>()
    private val mainHandler = Handler(Looper.getMainLooper())
    private var voiceLoaderTts: TextToSpeech? = null
    private val voiceOptions = mutableListOf<VoiceOption>()

    private val diagnosticsReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            if (intent?.action != VoiceAssistantService.ACTION_STATUS) return

            val engine = intent.getStringExtra("engine").orEmpty()
            val wakeHits = intent.getIntExtra("wake_hits", 0)
            val queriesSent = intent.getIntExtra("queries_sent", 0)
            val activeVoice = intent.getStringExtra("active_voice").orEmpty()
            val transcript = intent.getStringExtra("last_transcript").orEmpty()
            val confidence = intent.getFloatExtra("last_confidence", -1.0f)
            val error = intent.getStringExtra("last_error").orEmpty()
            val rtt = intent.getLongExtra("last_rtt_ms", -1L)
            val listening = intent.getBooleanExtra("listening", false)
            val audioDevice = intent.getStringExtra("audio_device").orEmpty()

            renderDiagnostics(
                engine = engine,
                listening = listening,
                activeVoice = activeVoice,
                wakeHits = wakeHits,
                queriesSent = queriesSent,
                transcript = transcript,
                confidence = confidence,
                error = error,
                rtt = rtt,
                audioDevice = audioDevice
            )
        }
    }

    private val diagnosticsPollRunnable = object : Runnable {
        override fun run() {
            val d = DiagnosticsStore.load(this@MainActivity)
            renderDiagnostics(
                engine = d.engine,
                listening = d.listening,
                activeVoice = d.activeVoice,
                wakeHits = d.wakeHits,
                queriesSent = d.queriesSent,
                transcript = d.lastTranscript,
                confidence = d.lastConfidence,
                error = d.lastError,
                rtt = d.lastRttMs,
                audioDevice = d.audioDevice
            )
            mainHandler.postDelayed(this, 1000L)
        }
    }

    private val requestPermissionsLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) {
        // User can still tap start again after permission result.
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        profiles.addAll(ServerProfileStore.defaultProfiles())
        ServerProfileStore.loadLastServer(this)?.let { profiles.add(0, it) }

        val labels = profiles.map { it.label }
        binding.profileSpinner.adapter = ArrayAdapter(
            this,
            android.R.layout.simple_spinner_dropdown_item,
            labels
        )

        binding.profileSpinner.setSelection(0)
        applyProfile(profiles[0])

        binding.profileSpinner.onItemSelected { _, _, position, _ ->
            applyProfile(profiles[position])
        }

        binding.fallbackSwitch.isChecked = false
        binding.diagnosticsText.text = "Waiting for service status..."
        setupVoiceSelector()

        binding.startButton.setOnClickListener {
            if (!hasRequiredPermissions()) {
                requestPermissions()
                return@setOnClickListener
            }

            val host = binding.hostInput.text?.toString()?.trim().orEmpty()
            val port = binding.portInput.text?.toString()?.toIntOrNull() ?: 8765
            if (host.isBlank()) {
                binding.hostLayout.error = "Host is required"
                return@setOnClickListener
            }
            binding.hostLayout.error = null

            val selectedVoiceName = currentSelectedVoiceName()
            VoicePreferenceStore.saveSelectedVoiceName(this, selectedVoiceName)

            ServerProfileStore.saveLastServer(this, host, port)
            startAssistantService(
                host = host,
                port = port,
                allowFallback = binding.fallbackSwitch.isChecked,
                voiceName = selectedVoiceName
            )
            binding.statusText.text = getString(R.string.status_running)
        }

        binding.stopButton.setOnClickListener {
            stopAssistantService()
            binding.statusText.text = getString(R.string.status_idle)
        }
    }

    override fun onStart() {
        super.onStart()
        registerReceiver(
            diagnosticsReceiver,
            IntentFilter(VoiceAssistantService.ACTION_STATUS),
            RECEIVER_NOT_EXPORTED
        )
        mainHandler.post(diagnosticsPollRunnable)
    }

    override fun onStop() {
        super.onStop()
        unregisterReceiver(diagnosticsReceiver)
        mainHandler.removeCallbacks(diagnosticsPollRunnable)
    }

    override fun onDestroy() {
        super.onDestroy()
        voiceLoaderTts?.shutdown()
        voiceLoaderTts = null
    }

    private fun renderDiagnostics(
        engine: String,
        listening: Boolean,
        activeVoice: String,
        wakeHits: Int,
        queriesSent: Int,
        transcript: String,
        confidence: Float,
        error: String,
        rtt: Long,
        audioDevice: String = "Unknown"
    ) {
        val diagnostics = buildString {
            appendLine("Engine: $engine")
            appendLine("Listening: $listening")
            appendLine("Audio device: $audioDevice")
            appendLine("Active voice: ${activeVoice.ifBlank { "-" }}")
            appendLine("Wake hits: $wakeHits")
            appendLine("Queries sent: $queriesSent")
            appendLine("Last RTT (ms): $rtt")
            appendLine("Last confidence: ${if (confidence < 0f) "-" else String.format("%.2f", confidence)}")
            appendLine("Last transcript: ${transcript.ifBlank { "-" }}")
            append("Last error: ${error.ifBlank { "-" }}")
        }
        binding.diagnosticsText.text = diagnostics
    }

    private fun applyProfile(profile: ServerProfile) {
        binding.hostInput.setText(profile.host)
        binding.portInput.setText(profile.port.toString())
    }

    private fun hasRequiredPermissions(): Boolean {
        val base = ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) ==
            PackageManager.PERMISSION_GRANTED
        val notifications = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) ==
                PackageManager.PERMISSION_GRANTED
        } else {
            true
        }
        return base && notifications
    }

    private fun requestPermissions() {
        val permissions = mutableListOf(Manifest.permission.RECORD_AUDIO)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            permissions.add(Manifest.permission.POST_NOTIFICATIONS)
        }
        requestPermissionsLauncher.launch(permissions.toTypedArray())
    }

    private fun startAssistantService(
        host: String,
        port: Int,
        allowFallback: Boolean,
        voiceName: String
    ) {
        val intent = Intent(this, VoiceAssistantService::class.java).apply {
            action = VoiceAssistantService.ACTION_START
            putExtra(VoiceAssistantService.EXTRA_HOST, host)
            putExtra(VoiceAssistantService.EXTRA_PORT, port)
            putExtra(VoiceAssistantService.EXTRA_ALLOW_ONLINE_FALLBACK, allowFallback)
            putExtra(VoiceAssistantService.EXTRA_VOICE_NAME, voiceName)
        }
        ContextCompat.startForegroundService(this, intent)
    }

    private fun stopAssistantService() {
        val intent = Intent(this, VoiceAssistantService::class.java).apply {
            action = VoiceAssistantService.ACTION_STOP
        }
        startService(intent)
    }

    private fun setupVoiceSelector() {
        val adapter = ArrayAdapter(this, android.R.layout.simple_spinner_dropdown_item, mutableListOf<String>())
        binding.voiceSpinner.adapter = adapter

        voiceOptions.clear()
        voiceOptions.add(VoiceOption(getString(R.string.voice_auto), ""))
        voiceOptions.add(
            VoiceOption(
                getString(R.string.voice_profile_uk_male),
                VoiceAssistantService.VOICE_PROFILE_UK_MALE
            )
        )
        voiceOptions.add(
            VoiceOption(
                getString(R.string.voice_profile_uk_female),
                VoiceAssistantService.VOICE_PROFILE_UK_FEMALE
            )
        )
        adapter.add(getString(R.string.voice_auto))
        adapter.add(getString(R.string.voice_profile_uk_male))
        adapter.add(getString(R.string.voice_profile_uk_female))
        adapter.notifyDataSetChanged()

        voiceLoaderTts = TextToSpeech(this) { status ->
            if (status != TextToSpeech.SUCCESS) {
                return@TextToSpeech
            }

            val voices = (voiceLoaderTts?.voices ?: emptySet())
                .asSequence()
                .filter { it.locale.language.equals("en", ignoreCase = true) }
                .sortedByDescending { voiceScore(it) }
                .take(25)
                .toList()

            runOnUiThread {
                voices.forEach { voice ->
                    val label = formatVoiceLabel(voice)
                    voiceOptions.add(VoiceOption(label, voice.name))
                    adapter.add(label)
                }
                adapter.notifyDataSetChanged()

                val preferredVoiceName = VoicePreferenceStore.loadSelectedVoiceName(this)
                val index = voiceOptions.indexOfFirst { it.voiceName == preferredVoiceName }
                binding.voiceSpinner.setSelection(if (index >= 0) index else 0)
            }
        }
    }

    private fun currentSelectedVoiceName(): String {
        val idx = binding.voiceSpinner.selectedItemPosition
        if (idx < 0 || idx >= voiceOptions.size) return ""
        return voiceOptions[idx].voiceName
    }

    private fun formatVoiceLabel(voice: Voice): String {
        val locale = voice.locale
        return "${locale.displayLanguage} (${locale.country}) - ${voice.name}"
    }

    private fun voiceScore(voice: Voice): Int {
        val name = voice.name.lowercase()
        val country = voice.locale.country.uppercase()

        var score = 0
        if (country == "GB") score += 100
        if (country == "US") score += 40
        if (name.contains("male") || name.contains("-m") || name.contains("_m")) score += 20
        if (name.contains("female") || name.contains("-f") || name.contains("_f")) score -= 10
        return score
    }

    private data class VoiceOption(
        val label: String,
        val voiceName: String
    )
}
