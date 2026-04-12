package com.earai.mobile

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import org.vosk.Model
import org.vosk.Recognizer
import org.vosk.android.RecognitionListener
import org.vosk.android.SpeechService
import java.io.File

class VoskOfflineEngine(
    private val context: Context,
    private val onWakePartial: (String) -> Unit,
    private val onFinalTranscript: (String, Float?) -> Unit,
    private val onError: (String) -> Unit
) {
    private var model: Model? = null
    private var recognizer: Recognizer? = null
    private var speechService: SpeechService? = null

    fun start(): Boolean {
        try {
            val modelDir = File(context.filesDir, MODEL_DIR_NAME)
            if (!modelDir.exists() || !modelDir.isDirectory) {
                onError("Offline model missing at ${modelDir.absolutePath}")
                return false
            }

            model = Model(modelDir.absolutePath)
            recognizer = Recognizer(model, SAMPLE_RATE_HZ).apply {
                setMaxAlternatives(3)
                setWords(true)
            }
            speechService = SpeechService(recognizer, SAMPLE_RATE_HZ).also {
                it.startListening(listener)
            }
            return true
        } catch (ex: Exception) {
            onError("Vosk init failed: ${ex.message}")
            stop()
            return false
        }
    }

    fun stop() {
        speechService?.stop()
        speechService?.shutdown()
        speechService = null

        recognizer?.close()
        recognizer = null

        model?.close()
        model = null
    }

    private val listener = object : RecognitionListener {
        override fun onPartialResult(hypothesis: String?) {
            val partial = TranscriptNormalizer.normalize(parseJsonField(hypothesis, "partial"))
            if (partial.isNotBlank()) {
                onWakePartial(partial)
            }
        }

        override fun onResult(hypothesis: String?) {
            val text = extractBestTranscript(hypothesis)
            if (text.isNotBlank()) {
                onFinalTranscript(text, parseAverageConfidence(hypothesis))
            }
        }

        override fun onFinalResult(hypothesis: String?) {
            val text = extractBestTranscript(hypothesis)
            if (text.isNotBlank()) {
                onFinalTranscript(text, parseAverageConfidence(hypothesis))
            }
        }

        override fun onError(exception: Exception?) {
            onError("Vosk error: ${exception?.message ?: "unknown"}")
        }

        override fun onTimeout() {
            // Restart capture to keep continuous pocket-mode listening active.
            speechService?.startListening(this)
        }
    }

    private fun parseJsonField(raw: String?, field: String): String {
        if (raw.isNullOrBlank()) return ""
        return try {
            JSONObject(raw).optString(field, "").trim()
        } catch (_: Exception) {
            ""
        }
    }

    private fun extractBestTranscript(raw: String?): String {
        if (raw.isNullOrBlank()) return ""

        return try {
            val json = JSONObject(raw)
            val alternatives = json.optJSONArray("alternatives")

            if (alternatives != null && alternatives.length() > 0) {
                val best = pickBestAlternative(alternatives)
                if (best.isNotBlank()) {
                    return TranscriptNormalizer.normalize(best)
                }
            }

            TranscriptNormalizer.normalize(json.optString("text", "").trim())
        } catch (_: Exception) {
            TranscriptNormalizer.normalize(parseJsonField(raw, "text"))
        }
    }

    private fun pickBestAlternative(alternatives: JSONArray): String {
        var bestText = ""
        var bestScore = -1.0

        for (i in 0 until alternatives.length()) {
            val item = alternatives.optJSONObject(i) ?: continue
            val text = item.optString("text", "").trim()
            if (text.isBlank()) continue

            val conf = item.optDouble("confidence", -1.0)
            val score = if (conf >= 0.0) conf else (text.length / 100.0)
            if (score > bestScore) {
                bestScore = score
                bestText = text
            }
        }

        return bestText
    }

    private fun parseAverageConfidence(raw: String?): Float? {
        if (raw.isNullOrBlank()) return null
        return try {
            val json = JSONObject(raw)
            val resultArray = json.optJSONArray("result") ?: return null
            if (resultArray.length() == 0) return null

            var sum = 0.0f
            var count = 0
            for (i in 0 until resultArray.length()) {
                val item = resultArray.optJSONObject(i) ?: continue
                val conf = item.optDouble("conf", -1.0)
                if (conf >= 0.0) {
                    sum += conf.toFloat()
                    count += 1
                }
            }
            if (count == 0) null else (sum / count)
        } catch (_: Exception) {
            null
        }
    }

    companion object {
        private const val SAMPLE_RATE_HZ = 16_000f
        const val MODEL_DIR_NAME = "vosk-model"
    }
}
