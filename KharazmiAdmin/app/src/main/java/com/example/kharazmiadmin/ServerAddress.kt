package com.example.kharazmiadmin

import java.net.URI

// FIX: Android HTTPS leftover - prefer TLS without guessing a public deployment hostname.
object ServerAddress {
    const val DEFAULT_ADDRESS = "https://192.168.1.5:8000/"

    fun normalize(value: String): String {
        val raw = value.trim()
        require(raw.isNotEmpty()) { "آدرس سرور خالی است" }
        val explicitScheme = raw.contains("://")
        val uri = URI(if (explicitScheme) raw else "https://$raw")
        val scheme = uri.scheme?.lowercase()
        require(scheme == "https" || scheme == "http") { "فقط آدرس HTTP یا HTTPS مجاز است" }
        val host = uri.host
        require(!host.isNullOrBlank() && uri.userInfo == null && uri.rawQuery == null && uri.rawFragment == null) {
            "آدرس پایهٔ سرور معتبر نیست؛ نام میزبان و پورت را بررسی کنید"
        }
        require(uri.port == -1 || uri.port in 1..65535) { "پورت سرور معتبر نیست" }
        // FIX: Keep the existing local-server port for bare IP/localhost inputs; domains default to HTTPS/443.
        val localAddress = host.equals("localhost", ignoreCase = true) || host.contains(':') ||
            host.matches(Regex("[0-9]+(?:\\.[0-9]+){3}"))
        val port = if (!explicitScheme && uri.port == -1 && localAddress) 8000 else uri.port
        val path = (uri.path ?: "").let { if (it.endsWith('/')) it else "$it/" }
        return URI(scheme, null, host, port, path, null, null).toASCIIString()
    }
}

