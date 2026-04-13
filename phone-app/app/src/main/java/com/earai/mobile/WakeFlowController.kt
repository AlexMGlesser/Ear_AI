package com.earai.mobile

class WakeFlowController(
    private val wakePhrase: String = "dante"
) {
    private var state: State = State.WAITING_WAKE

    enum class State {
        WAITING_WAKE,
        WAITING_QUERY
    }

    fun currentState(): State = state

    fun detectWakePhrase(text: String): Boolean {
        if (state != State.WAITING_WAKE) return false
        val normalized = TranscriptNormalizer.normalize(text)
        val found = TranscriptNormalizer.containsWakeLikeToken(normalized)
        if (found) {
            state = State.WAITING_QUERY
        }
        return found
    }

    fun consumeUtterance(rawText: String): String? {
        if (state != State.WAITING_QUERY) return null

        val text = TranscriptNormalizer
            .stripWakeWords(rawText)
            .trim()

        if (text.isBlank()) {
            return ""
        }

        state = State.WAITING_WAKE
        return text
    }

    fun resetToWake() {
        state = State.WAITING_WAKE
    }
}
