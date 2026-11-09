package com.example.kharazmiadmin

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.print.PrintAttributes
import android.print.PrintManager
import android.webkit.WebView
import android.widget.Toast
import androidx.core.content.FileProvider
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.ResponseBody
import retrofit2.http.GET
import retrofit2.http.Streaming
import retrofit2.http.Url
import java.io.File
import java.io.FileOutputStream

// کلاینت دانلود فایل رتروفیت
interface DownloadApi {
    @Streaming
    @GET
    suspend fun downloadFile(@Url url: String): ResponseBody
}

object ReportExporter {

    // ۱. منطق هوشمند چاپ مستقیم PDF برای گزارش‌های جدولی کلاینت‌ساید (با پشتیبانی کامل از RTL فارسی و صفحات متوالی)
    fun printPdfReport(
        context: Context,
        title: String,
        headers: List<String>,
        rows: List<List<String>>
    ) {
        val webView = WebView(context)
        val sb = StringBuilder()
        sb.append("""
            <html>
            <head>
                <meta charset="UTF-8">
                <style>
                    body { font-family: 'Tahoma', sans-serif; direction: rtl; padding: 20px; }
                    .header { text-align: center; border-bottom: 2px solid #00695C; padding-bottom: 10px; margin-bottom: 20px; }
                    .title { font-size: 20px; font-weight: bold; color: #00695C; }
                    table { width: 100%; border-collapse: collapse; margin-top: 15px; }
                    th, td { border: 1px solid #ddd; padding: 8dp; text-align: center; font-size: 12px; }
                    th { background-color: #00695C; color: white; font-weight: bold; }
                    tr:nth-child(even) { background-color: #f9f9f9; }
                    .footer { margin-top: 30px; text-align: center; font-size: 11px; color: #777; }
                </style>
            </head>
            <body>
                <div class="header">
                    <div class="title">$title</div>
                </div>
                <table>
                    <thead>
                        <tr>
        """)

        for (h in headers) {
            sb.append("<th>$h</th>")
        }

        sb.append("""
                        </tr>
                    </thead>
                    <tbody>
        """)

        for (row in rows) {
            sb.append("<tr>")
            for (cell in row) {
                sb.append("<td>$cell</td>")
            }
            sb.append("</tr>")
        }

        sb.append("""
                    </tbody>
                </table>
                <div class="footer">
                    ${context.getString(R.string.rexp_footer)}
                </div>
            </body>
            </html>
        """)

        webView.loadDataWithBaseURL(null, sb.toString(), "text/html", "UTF-8", null)

        val printManager = context.getSystemService(Context.PRINT_SERVICE) as PrintManager
        val printAdapter = webView.createPrintDocumentAdapter("Report_${System.currentTimeMillis()}")
        
        val printAttributes = PrintAttributes.Builder()
            .setMediaSize(PrintAttributes.MediaSize.ISO_A4)
            .build()
            
        printManager.print("Kharazmi_Report_${System.currentTimeMillis()}", printAdapter, printAttributes)
    }

    // ۲. دانلود و اشتراک‌گذاری فایل Excel از سرور با FileProvider اختصاصی
    fun exportToExcel(
        context: Context,
        endpointUrl: String,
        fileName: String,
        onStart: () -> Unit,
        onComplete: () -> Unit,
        onError: (String) -> Unit,
        mimeType: String = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    ) {
        // FIX: Bug 19 - never create an unowned background job from a UI helper.
        val owner = context as? LifecycleOwner
        if (owner == null) {
            onError(context.getString(R.string.rexp_no_page))
            return
        }
        onStart()
        
        val retrofit = RetrofitClient.getInstance(context)
        val api = retrofit.create(DownloadApi::class.java)

        // FIX: Bug 19 - export is cancelled with the screen that requested it.
        owner.lifecycleScope.launch(Dispatchers.IO) {
            try {
                val responseBody = api.downloadFile(endpointUrl)
                
                // ذخیره فیزیکی فایل در پوشه بیرونی امن اپلیکیشن
                val destinationFile = File(context.getExternalFilesDir(null), fileName)
                // FIX: Bug 19 - cooperate with cancellation and close streams on cancellation/errors.
                responseBody.use { body ->
                    body.byteStream().use { inputStream ->
                        FileOutputStream(destinationFile).use { outputStream ->
                            val buffer = ByteArray(4096)
                            while (true) {
                                coroutineContext.ensureActive()
                                val bytesRead = inputStream.read(buffer)
                                if (bytesRead == -1) break
                                outputStream.write(buffer, 0, bytesRead)
                            }
                        }
                    }
                }

                withContext(Dispatchers.Main) {
                    onComplete()
                    
                    // دریافت URI با اختیارات FileProvider
                    val fileUri: Uri = FileProvider.getUriForFile(
                        context,
                        "com.example.kharazmiadmin.provider",
                        destinationFile
                    )

                    // نمایش دیالوگ اشتراک‌گذاری/بازکردن فایل Excel
                    val intent = Intent(Intent.ACTION_SEND).apply {
                        type = mimeType
                        putExtra(Intent.EXTRA_STREAM, fileUri)
                        addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                    }
                    
                    context.startActivity(Intent.createChooser(intent, context.getString(R.string.rexp_share_title)))
                }
            } catch (e: Exception) {
                // FIX: Bug 19 - cancellation must not open UI callbacks on a destroyed screen.
                if (e is kotlinx.coroutines.CancellationException) throw e
                withContext(Dispatchers.Main) {
                    onError(e.message ?: context.getString(R.string.rexp_server_error))
                }
            }
        }
    }
}
