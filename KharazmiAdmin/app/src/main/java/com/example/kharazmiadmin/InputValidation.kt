package com.example.kharazmiadmin

// FIX: Bug 22 - reusable, non-throwing validation for Android identity and numeric inputs.
object InputValidation {
    fun normalizeDigits(value: String): String = value.trim().map { char ->
        when (char) {
            in '۰'..'۹' -> '0' + (char - '۰')
            in '٠'..'٩' -> '0' + (char - '٠')
            else -> char
        }
    }.joinToString("")

    fun isValidNationalCode(value: String): Boolean {
        val code = normalizeDigits(value)
        if (code.length != 10 || code.any { it !in '0'..'9' } || code.toSet().size == 1) return false
        val remainder = (0..8).sumOf { (code[it] - '0') * (10 - it) } % 11
        return code.last() - '0' == if (remainder < 2) remainder else 11 - remainder
    }

    fun nonNegativeAmount(value: String): Long? =
        normalizeDigits(value).toLongOrNull()?.takeIf { it >= 0 }

    // FIX: Bug 22 - permit explicit zero shares, but require a positive, non-overflowing total.
    fun paymentTotal(first: Long, second: Long = 0): Long? {
        if (first < 0 || second < 0 || first > Long.MAX_VALUE - second) return null
        return (first + second).takeIf { it > 0 }
    }

    fun isValidScore(score: Float, maxScore: Float): Boolean =
        score.isFinite() && maxScore.isFinite() && maxScore > 0 && score >= 0 && score <= maxScore
}

