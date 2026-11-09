# DunningActivity

- Kotlin: `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/DunningActivity.kt:23`
- layout و محل bind:
  - `R.layout.activity_dunning` در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/DunningActivity.kt:41`؛ فایل `KharazmiAdmin/app/src/main/res/layout/activity_unning.xml:1` در صورت وجود.

> این سند از جست‌وجوی محتوای source ساخته شده است. هر موردی که source آن را صریح نکرده با «نامشخص» آمده و حدس زده نشده است. Android compile اجرا نشده است.

## عناصر تعاملی، API و navigation

| خط | id صریح نزدیک handler | سطر handler/transition | route قابل اتصال |
|---:|---|---|---|
| 70 | `id نامشخص` | `btnSelectAll.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 76 | `id نامشخص` | `btnDeselectAll.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 81 | `id نامشخص` | `btnRefresh.setOnClickListener { loadDrafts() }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 82 | `id نامشخص` | `btnBack.setOnClickListener { finish() }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 84 | `id نامشخص` | `fabSend.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 86 | `id نامشخص` | `Toast.makeText(this, getString(R.string.dunning_no_selection), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 87 | `id نامشخص` | `return@setOnClickListener` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 148 | `id نامشخص` | `Toast.makeText(this@DunningActivity, msg, Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 171 | `id نامشخص` | `Toast.makeText(this@DunningActivity, msg, Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 194 | `id نامشخص` | `Toast.makeText(this@DunningActivity, msg, Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 251 | `id نامشخص` | `holder.cbSelect.setOnCheckedChangeListener(null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 253 | `id نامشخص` | `holder.cbSelect.setOnCheckedChangeListener { _, isChecked ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 258 | `id نامشخص` | `holder.card.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |

## تماس‌های سرور در این فایل

| خط | فراخوانی | method/path از CSV فاز B |
|---:|---|---|
| 117 | `val list = api.getDrafts()` | `GET dunning/drafts` |
| 162 | `val resp = api.sendBatch(DunningSendRequest(idsToSend))` | `POST dunning/send_batch` |

## داده‌های نمایشی و محاسبهٔ سمت اپ

| خط | assignment/render | منشأ قابل اثبات |
|---:|---|---|
| 61 | `tvTitle.text = getString(R.string.dunning_title)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 94 | `fabSend.text = if (selectedIds.isEmpty()) {` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 110 | `tvEmpty.text = getString(R.string.dunning_loading)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 124 | `tvEmpty.text = getString(R.string.dunning_empty)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 130 | `rvDrafts.adapter = DunningAdapter(list)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 145 | `tvEmpty.text = msg` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 156 | `tvEmpty.text = getString(R.string.dunning_sending)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 195 | `tvEmpty.text = msg` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 225 | `holder.tvStudentName.text = item.studentName` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 226 | `holder.tvAmount.text = formatAmount(item.amount)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 227 | `holder.tvDueDate.text = "سررسید: ${item.dueDate}"` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 228 | `holder.tvParentMobile.text = "📱 ${item.parentMobile}"` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 229 | `holder.tvSmsPreview.text = item.suggestedMessage` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 245 | `holder.tvCategory.text = statusText` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |

## مراجع تکمیلی

- API declarationها و type فیلدها: [`../android-api-calls.csv`](../android-api-calls.csv).
- route و handler سمت سرور: [`../server-routes.csv`](../server-routes.csv).
