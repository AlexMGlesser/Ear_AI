package com.earai.mobile

object TranscriptNormalizer {
    private val replacements = listOf(
        Regex("\\bdon\\s*t\\b", RegexOption.IGNORE_CASE) to "dante",
        Regex("\\bdonte\\b", RegexOption.IGNORE_CASE) to "dante",
        Regex("\\bdanty\\b", RegexOption.IGNORE_CASE) to "dante",
        Regex("\\bdanteh\\b", RegexOption.IGNORE_CASE) to "dante",
        Regex("\\bdan\\s*tea\\b", RegexOption.IGNORE_CASE) to "dante",
        Regex("\\bdanti\\b", RegexOption.IGNORE_CASE) to "dante",
        Regex("\\bdantee\\b", RegexOption.IGNORE_CASE) to "dante",
        Regex("\\bdahnte\\b", RegexOption.IGNORE_CASE) to "dante",
        Regex("\\bdaante\\b", RegexOption.IGNORE_CASE) to "dante",
        Regex("\\bdunty\\b", RegexOption.IGNORE_CASE) to "dante"
    )

    private val wakeAliases = setOf(
        "dante",
        "donte",
        "danty",
        "danti",
        "dantee",
        "danteh",
        "dahnte",
        "daante",
        "dunty",
    )

    fun normalize(text: String): String {
        var output = text.trim()
        replacements.forEach { (pattern, replacement) ->
            output = pattern.replace(output, replacement)
        }

        output = output
            .replace(Regex("\\s+"), " ")
            .trim()

        return output
    }

    fun containsWakeLikeToken(text: String): Boolean {
        val normalized = normalize(text).lowercase()
        val tokens = normalized.split(Regex("[^a-z]+")).filter { it.isNotBlank() }
        return tokens.any { token ->
            token in wakeAliases || levenshtein(token, "dante") <= 1
        }
    }

    fun stripWakeWords(text: String): String {
        val normalized = normalize(text)
        val builder = StringBuilder()
        normalized.split(Regex("\\s+")).forEach { word ->
            val cleaned = word.lowercase().replace(Regex("[^a-z]"), "")
            val isWake = cleaned.isNotBlank() && (cleaned in wakeAliases || levenshtein(cleaned, "dante") <= 1)
            if (!isWake) {
                if (builder.isNotEmpty()) builder.append(' ')
                builder.append(word)
            }
        }
        return builder.toString().trim()
    }

    private fun levenshtein(a: String, b: String): Int {
        if (a == b) return 0
        if (a.isEmpty()) return b.length
        if (b.isEmpty()) return a.length

        val prev = IntArray(b.length + 1) { it }
        val curr = IntArray(b.length + 1)

        for (i in a.indices) {
            curr[0] = i + 1
            for (j in b.indices) {
                val cost = if (a[i] == b[j]) 0 else 1
                curr[j + 1] = minOf(
                    curr[j] + 1,
                    prev[j + 1] + 1,
                    prev[j] + cost
                )
            }
            for (k in prev.indices) {
                prev[k] = curr[k]
            }
        }

        return prev[b.length]
    }
}
