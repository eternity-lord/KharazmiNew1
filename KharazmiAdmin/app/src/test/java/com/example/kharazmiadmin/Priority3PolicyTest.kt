package com.example.kharazmiadmin

import org.junit.Assert.*
import org.junit.Test

// FIX: Priority 3 - run the real pure policies on the JVM, without an emulator or copied business logic.
class Priority3PolicyTest {
    @Test fun cacheIsFreshOnlyBeforeFiveMinutes() {
        val saved = 1_000_000L
        assertTrue(CachePolicy.isFresh(saved, saved))
        assertTrue(CachePolicy.isFresh(saved, saved + 299_999))
        assertFalse(CachePolicy.isFresh(saved, saved + 300_000))
        assertFalse(CachePolicy.isFresh(saved, saved + 300_001))
    }

    @Test fun cacheRejectsMissingTimestampsAndClockRollback() {
        assertFalse(CachePolicy.isFresh(0, 1_000_000))
        assertFalse(CachePolicy.isFresh(-1, 1_000_000))
        assertFalse(CachePolicy.isFresh(1_000_001, 1_000_000))
        assertFalse(CachePolicy.isFresh(Long.MAX_VALUE, 1_000_000))
        assertFalse(CachePolicy.isFresh(1, 2, 0))
    }

    @Test fun nationalCodeRequiresChecksumAndPreservesLeadingZeroes() {
        assertTrue(InputValidation.isValidNationalCode("0012345679"))
        assertTrue(InputValidation.isValidNationalCode("0001112228"))
        assertFalse(InputValidation.isValidNationalCode("0012345678"))
        assertFalse(InputValidation.isValidNationalCode("1234567890"))
        assertFalse(InputValidation.isValidNationalCode("1111111111"))
        assertFalse(InputValidation.isValidNationalCode("0000000000"))
        assertFalse(InputValidation.isValidNationalCode("123"))
    }

    @Test fun nationalCodeAcceptsSupportedKeyboardDigitsButNotArbitraryUnicode() {
        assertTrue(InputValidation.isValidNationalCode(" ۰۰۱۲۳۴۵۶۷۹ "))
        assertTrue(InputValidation.isValidNationalCode("٠٠١٢٣٤٥٦٧٩"))
        assertEquals("0012345679", InputValidation.normalizeDigits("۰۰۱۲۳۴۵۶۷۹"))
        assertFalse(InputValidation.isValidNationalCode("²012345679"))
        assertFalse(InputValidation.isValidNationalCode("00123a5679"))
        assertFalse(InputValidation.isValidNationalCode("00123 5679"))
    }

    @Test fun amountParsingNeverThrowsForBadOrOverflowingInput() {
        assertNull(InputValidation.nonNegativeAmount(""))
        assertNull(InputValidation.nonNegativeAmount("not a number"))
        assertNull(InputValidation.nonNegativeAmount("-1"))
        assertNull(InputValidation.nonNegativeAmount("9223372036854775808"))
        assertEquals(0L, InputValidation.nonNegativeAmount("0"))
        assertEquals(100L, InputValidation.nonNegativeAmount(" ۱۰۰ "))
        assertEquals(Long.MAX_VALUE, InputValidation.nonNegativeAmount(Long.MAX_VALUE.toString()))
    }

    @Test fun paymentTotalIsPositiveAndSharesMayExplicitlyBeZero() {
        assertNull(InputValidation.paymentTotal(0))
        assertNull(InputValidation.paymentTotal(0, 0))
        assertNull(InputValidation.paymentTotal(-1, 100))
        assertNull(InputValidation.paymentTotal(100, -1))
        assertEquals(100L, InputValidation.paymentTotal(0, 100))
        assertEquals(100L, InputValidation.paymentTotal(100, 0))
        assertEquals(101L, InputValidation.paymentTotal(50, 51))
    }

    @Test fun paymentTotalCannotOverflowLong() {
        assertNull(InputValidation.paymentTotal(Long.MAX_VALUE, 1))
        assertNull(InputValidation.paymentTotal(1, Long.MAX_VALUE))
        assertEquals(Long.MAX_VALUE, InputValidation.paymentTotal(Long.MAX_VALUE, 0))
        assertEquals(Long.MAX_VALUE, InputValidation.paymentTotal(Long.MAX_VALUE - 1, 1))
    }

    @Test fun scoreBoundariesAreInclusiveAndMaximumPositive() {
        assertTrue(InputValidation.isValidScore(0f, 20f))
        assertTrue(InputValidation.isValidScore(20f, 20f))
        assertTrue(InputValidation.isValidScore(1.5f, 2f))
        assertFalse(InputValidation.isValidScore(21f, 20f))
        assertFalse(InputValidation.isValidScore(-1f, 20f))
        assertFalse(InputValidation.isValidScore(0f, 0f))
    }

    @Test fun nonFiniteScoresAreRejected() {
        assertFalse(InputValidation.isValidScore(Float.NaN, 20f))
        assertFalse(InputValidation.isValidScore(Float.POSITIVE_INFINITY, 20f))
        assertFalse(InputValidation.isValidScore(10f, Float.POSITIVE_INFINITY))
        assertFalse(InputValidation.isValidScore(10f, Float.NaN))
    }

    @Test fun bareDomainsPreferHttpsWithoutLocalPort() {
        assertEquals("https://school.example/", ServerAddress.normalize("school.example"))
        assertEquals("https://school.example/api/", ServerAddress.normalize("school.example/api"))
        assertEquals("https://school.example:8443/api/", ServerAddress.normalize("school.example:8443/api/"))
    }

    @Test fun bareLocalAddressesKeepThePortButUpgradeToHttps() {
        assertEquals("https://192.168.1.5:8000/", ServerAddress.normalize("192.168.1.5"))
        assertEquals("https://localhost:8000/", ServerAddress.normalize("localhost"))
        assertEquals("https://[::1]:8000/", ServerAddress.normalize("[::1]"))
        assertTrue(ServerAddress.DEFAULT_ADDRESS.startsWith("https://"))
    }

    @Test fun explicitHttpsAndWarnedHttpArePreserved() {
        assertEquals("https://school.example/", ServerAddress.normalize("https://school.example"))
        assertEquals("https://school.example:8443/api/", ServerAddress.normalize("HTTPS://school.example:8443/api"))
        assertEquals("http://192.168.1.5:8000/", ServerAddress.normalize("http://192.168.1.5:8000"))
    }

    @Test fun malformedOrCredentialBearingAddressesAreRejected() {
        for (value in listOf("", "http://", "ftp://school.example/", "https://user:pass@school.example/", "https://school.example/?secret=123", "https://school.example/#fragment", "school.example:70000", "not a host")) {
            try {
                ServerAddress.normalize(value)
                fail("Expected invalid base URL: $value")
            } catch (expected: Exception) {
                // FIX: Invalid input is returned to the settings UI, not accepted as an insecure fallback.
            }
        }
    }
}

