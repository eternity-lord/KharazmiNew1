package com.example.kharazmiadmin

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

// FIX: Bugs 19/21 - the caller supplies its lifecycle scope; delay and request share one cancellable job.
class DebouncedRequest(private val ownerScope: CoroutineScope) {
    private var currentJob: Job? = null

    fun submit(debounce: Boolean = true, request: suspend () -> Unit) {
        currentJob?.cancel()
        currentJob = ownerScope.launch {
            if (debounce) delay(400)
            request()
        }
    }
}

