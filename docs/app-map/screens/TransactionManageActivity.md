# TransactionManageActivity

- Kotlin: `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/TransactionManageActivity.kt:39`
- layout و محل bind:
  - `R.layout.activity_transaction_manage` در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/TransactionManageActivity.kt:47`؛ فایل `KharazmiAdmin/app/src/main/res/layout/activity_ransaction_manage.xml:1` در صورت وجود.

> این سند از جست‌وجوی محتوای source ساخته شده است. هر موردی که source آن را صریح نکرده با «نامشخص» آمده و حدس زده نشده است. Android compile اجرا نشده است.

## عناصر تعاملی، API و navigation

| خط | id صریح نزدیک handler | سطر handler/transition | route قابل اتصال |
|---:|---|---|---|
| 62 | `btnExportExcel` | `findViewById<MaterialButton>(R.id.btnExportExcel).setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 68 | `id نامشخص` | `Toast.makeText(this, getString(R.string.txn_excel_start), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 71 | `id نامشخص` | `Toast.makeText(this, getString(R.string.txn_excel_done), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 74 | `id نامشخص` | `Toast.makeText(this, getString(R.string.txn_excel_error, errorMsg), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 80 | `btnExportPdf` | `findViewById<MaterialButton>(R.id.btnExportPdf).setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 82 | `btnExportPdf` | `Toast.makeText(this, getString(R.string.txn_print_empty), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 83 | `id نامشخص` | `return@setOnClickListener` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 128 | `id نامشخص` | `Toast.makeText(this@TransactionManageActivity, getString(R.string.common_list_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 169 | `id نامشخص` | `holder.btnDelete.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 173 | `id نامشخص` | `.setPositiveButton(getString(R.string.action_delete)) { _, _ -> deleteItem(item.id) }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 174 | `id نامشخص` | `.setNegativeButton(getString(R.string.common_cancel), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 175 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 179 | `id نامشخص` | `holder.btnEdit.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 184 | `id نامشخص` | `holder.btnPrint.setOnClickListener {` | Intent → InvoiceActivity |
| 189 | `id نامشخص` | `startActivity(intent)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 204 | `id نامشخص` | `Toast.makeText(this@TransactionManageActivity, getString(R.string.common_ok_msg, res.message), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 210 | `id نامشخص` | `withContext(Dispatchers.Main) { Toast.makeText(this@TransactionManageActivity, getString(R.string.txn_del_error), Toast.LENGTH_SHORT).show() }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 225 | `id نامشخص` | `.setPositiveButton(getString(R.string.action_save)) { _, _ ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 231 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 241 | `id نامشخص` | `Toast.makeText(this@TransactionManageActivity, getString(R.string.txn_edit_done), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 250 | `id نامشخص` | `startActivity(intent)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 256 | `id نامشخص` | `withContext(Dispatchers.Main) { Toast.makeText(this@TransactionManageActivity, getString(R.string.txn_edit_error), Toast.LENGTH_SHORT).show() }` | route از context همین سطر/سطرهای مجاور مشخص نیست |

## تماس‌های سرور در این فایل

| خط | فراخوانی | method/path از CSV فاز B |
|---:|---|---|
| 113 | `val list = api.getTransactions(query)` | `GET admin/transactions/list` |
| 202 | `val res = api.deleteTransaction(id)` | `DELETE admin/transactions/{id}` |
| 239 | `api.updateTransaction(id, data)` | `PUT admin/transactions/{id}` |

## داده‌های نمایشی و محاسبهٔ سمت اپ

| خط | assignment/render | منشأ قابل اثبات |
|---:|---|---|
| 50 | `findViewById<TextView>(R.id.tvHeaderTitle)?.text = getString(R.string.txn_title)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 121 | `rv.adapter = TransManageAdapter(list)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 122 | `findViewById<TextView>(R.id.tvTotalSum)?.text = getString(R.string.common_toman_format, totalSum)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 156 | `holder.tvName.text = "${item.student_name}$remittanceStr"` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 157 | `holder.tvCourse.text = getString(R.string.txn_course_row, item.course_name, item.description ?: "")` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 158 | `holder.tvAmount.text = getString(R.string.txn_amount_row, String.format("%,d", item.amount))` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 159 | `holder.tvDate.text = item.date` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 220 | `etInput.setText(item.amount.toString())` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |

## مراجع تکمیلی

- API declarationها و type فیلدها: [`../android-api-calls.csv`](../android-api-calls.csv).
- route و handler سمت سرور: [`../server-routes.csv`](../server-routes.csv).
