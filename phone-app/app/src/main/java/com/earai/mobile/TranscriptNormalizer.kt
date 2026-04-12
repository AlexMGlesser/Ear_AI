package com.earai.mobile

object TranscriptNormalizer {
    private val replacements = listOf(
        Regex("\\bdon\\s*t\\b", RegexOption.IGNORE_CASE) to "dante",
        Regex("\\bdonte\\b", RegexOption.IGNORE_CASE) to "dante",
        Regex("\\bdanty\\b", RegexOption.IGNORE_CASE) to "dante",
        Regex("\\bdanteh\\b", RegexOption.IGNORE_CASE) to "dante",
        Regex("\\bdan\\s*tea\\b", RegexOption.IGNORE_CASE) to "dante"
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
}
