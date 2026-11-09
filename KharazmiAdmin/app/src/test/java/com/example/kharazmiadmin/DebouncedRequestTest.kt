package com.example.kharazmiadmin

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import org.junit.Assert.*
import org.junit.Test

// FIX: Bugs 19/21 - exercise the real request controller with virtual time, not sleeps or copied debounce logic.
@OptIn(ExperimentalCoroutinesApi::class)
class DebouncedRequestTest {
    @Test fun waitsFourHundredMillisecondsBeforeRequest() = runTest {
        val requests = DebouncedRequest(this)
        var calls = 0
        requests.submit { calls++ }
        advanceTimeBy(399)
        runCurrent()
        assertEquals(0, calls)
        advanceTimeBy(1)
        runCurrent()
        assertEquals(1, calls)
    }

    @Test fun fastTypingOnlyRequestsLastQuery() = runTest {
        val requests = DebouncedRequest(this)
        val received = mutableListOf<String>()
        requests.submit { received += "a" }
        advanceTimeBy(200)
        requests.submit { received += "ab" }
        advanceTimeBy(200)
        requests.submit { received += "abc" }
        advanceUntilIdle()
        assertEquals(listOf("abc"), received)
    }

    @Test fun newQueryCancelsAnAlreadyRunningRequest() = runTest {
        val requests = DebouncedRequest(this)
        val results = mutableListOf<String>()
        requests.submit(debounce = false) { delay(2000); results += "old" }
        runCurrent()
        requests.submit { results += "new" }
        advanceUntilIdle()
        assertEquals(listOf("new"), results)
    }

    @Test fun refreshBypassesDelayAndCancelsPendingTyping() = runTest {
        val requests = DebouncedRequest(this)
        val results = mutableListOf<String>()
        requests.submit { results += "pending typing" }
        advanceTimeBy(100)
        requests.submit(debounce = false) { results += "refresh" }
        runCurrent()
        assertEquals(listOf("refresh"), results)
        advanceUntilIdle()
        assertEquals(listOf("refresh"), results)
    }

    @Test fun ownerCancellationStopsDelayAndNetworkWork() = runTest {
        val owner = CoroutineScope(coroutineContext + SupervisorJob())
        val requests = DebouncedRequest(owner)
        var callbacks = 0
        requests.submit(debounce = false) { delay(1000); callbacks++ }
        runCurrent()
        owner.cancel()
        advanceUntilIdle()
        assertEquals(0, callbacks)
        requests.submit { callbacks++ }
        advanceUntilIdle()
        assertEquals(0, callbacks)
    }
}

