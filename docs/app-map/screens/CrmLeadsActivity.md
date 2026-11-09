# CrmLeadsActivity

- Kotlin: `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/CrmLeadsActivity.kt:66`
- layout و محل bind:
  - `R.layout.activity_crm_leads` در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/CrmLeadsActivity.kt:91`؛ فایل `KharazmiAdmin/app/src/main/res/layout/activity_rm_leads.xml:1` در صورت وجود.

> این سند از جست‌وجوی محتوای source ساخته شده است. هر موردی که source آن را صریح نکرده با «نامشخص» آمده و حدس زده نشده است. Android compile اجرا نشده است.

## عناصر تعاملی، API و navigation

| خط | id صریح نزدیک handler | سطر handler/transition | route قابل اتصال |
|---:|---|---|---|
| 126 | `id نامشخص` | `btnSubmit.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 132 | `id نامشخص` | `Toast.makeText(this, getString(R.string.crm_fill), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 133 | `id نامشخص` | `return@setOnClickListener` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 139 | `id نامشخص` | `btnSaveNotes.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 144 | `id نامشخص` | `Toast.makeText(this, getString(R.string.crm_note_empty), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 145 | `id نامشخص` | `return@setOnClickListener` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 151 | `id نامشخص` | `btnConvert.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 155 | `id نامشخص` | `.setPositiveButton(getString(R.string.crm_conv_yes)) { _, _ ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 158 | `id نامشخص` | `.setNegativeButton(getString(R.string.common_cancel), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 159 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 162 | `id نامشخص` | `btnBack.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 182 | `id نامشخص` | `Toast.makeText(this@CrmLeadsActivity, getString(R.string.crm_lead_done), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 195 | `id نامشخص` | `Toast.makeText(this@CrmLeadsActivity, msg, Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 221 | `id نامشخص` | `Toast.makeText(this@CrmLeadsActivity, getString(R.string.crm_lead_empty), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 231 | `id نامشخص` | `Toast.makeText(this@CrmLeadsActivity, getString(R.string.crm_leads_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 257 | `id نامشخص` | `Toast.makeText(this@CrmLeadsActivity, getString(R.string.crm_note_done), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 265 | `id نامشخص` | `Toast.makeText(this@CrmLeadsActivity, getString(R.string.crm_note_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 277 | `id نامشخص` | `Toast.makeText(this@CrmLeadsActivity, getString(R.string.common_ok_msg, res.message), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 292 | `id نامشخص` | `Toast.makeText(this@CrmLeadsActivity, msg, Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 323 | `id نامشخص` | `holder.itemView.setOnClickListener { onClick(item) }` | route از context همین سطر/سطرهای مجاور مشخص نیست |

## تماس‌های سرور در این فایل

| خط | فراخوانی | method/path از CSV فاز B |
|---:|---|---|
| 180 | `api.createLead(req)` | `POST crm/leads/create` |
| 218 | `val list = api.getLeadsList()` | `GET crm/leads/list` |
| 255 | `api.addNotes(activeLeadId, req)` | `POST crm/leads/{id}/notes` |
| 275 | `val res = api.convertLead(activeLeadId)` | `POST crm/leads/{id}/convert` |

## داده‌های نمایشی و محاسبهٔ سمت اپ

| خط | assignment/render | منشأ قابل اثبات |
|---:|---|---|
| 183 | `etName.text = null` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 184 | `etMobile.text = null` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 185 | `etCourse.text = null` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 223 | `rvLeads.adapter = LeadsAdapter(list) { lead ->` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 241 | `tvDetailName.text = getString(R.string.crm_det_name, lead.name)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 242 | `tvDetailMobile.text = getString(R.string.crm_det_mobile, lead.mobile)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 243 | `tvDetailCourse.text = getString(R.string.crm_det_course, lead.interested_course)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 244 | `tvDetailStatus.text = getString(R.string.crm_det_status, lead.status)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 246 | `etNotesInput.setText(lead.notes ?: "")` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 247 | `etNextFollowUp.setText(lead.next_follow_up ?: "")` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 318 | `holder.name.text = holder.itemView.context.getString(R.string.common_person_row, item.name)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 319 | `holder.course.text = holder.itemView.context.getString(R.string.crm_row_course, item.interested_course)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 320 | `holder.followUp.text = holder.itemView.context.getString(R.string.crm_row_follow, item.next_follow_up ?: holder.itemView.context.getString(R.string.crm_unset))` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 321 | `holder.status.text = item.status` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |

## مراجع تکمیلی

- API declarationها و type فیلدها: [`../android-api-calls.csv`](../android-api-calls.csv).
- route و handler سمت سرور: [`../server-routes.csv`](../server-routes.csv).
