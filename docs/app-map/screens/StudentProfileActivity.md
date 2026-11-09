# StudentProfileActivity

- Kotlin: `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/StudentProfileActivity.kt:120`
- layout و محل bind:
  - `R.layout.activity_student_profile` در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/StudentProfileActivity.kt:160`؛ فایل `KharazmiAdmin/app/src/main/res/layout/activity_tudent_profile.xml:1` در صورت وجود.

> این سند از جست‌وجوی محتوای source ساخته شده است. هر موردی که source آن را صریح نکرده با «نامشخص» آمده و حدس زده نشده است. Android compile اجرا نشده است.

## عناصر تعاملی، API و navigation

| خط | id صریح نزدیک handler | سطر handler/transition | route قابل اتصال |
|---:|---|---|---|
| 164 | `id نامشخص` | `Toast.makeText(this, getString(R.string.profile_id_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 165 | `id نامشخص` | `finish()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 214 | `fabEditProfile` | `findViewById<FloatingActionButton>(R.id.fabEditProfile).setOnClickListener {` | Intent → EditStudentActivity |
| 217 | `id نامشخص` | `startActivity(intent)` | Intent → EditStudentActivity |
| 297 | `btnDeleteStudent` | `btnAddInstallment.setOnClickListener { showCreateInstallmentDialog() }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 299 | `btnDeleteStudent` | `findViewById<MaterialButton>(R.id.btnDeleteStudent).setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 303 | `btnSendPortalLink` | `findViewById<MaterialButton>(R.id.btnSendPortalLink).setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 307 | `imgProfile` | `findViewById<android.widget.ImageView>(R.id.imgProfile).setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 311 | `id نامشخص` | `switchSuspend.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 315 | `id نامشخص` | `btnInvoice.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 364 | `id نامشخص` | `switchSuspend.setOnCheckedChangeListener(null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 366 | `id نامشخص` | `switchSuspend.setOnClickListener { toggleStudentSuspension() }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 417 | `id نامشخص` | `.setItems(labels.toTypedArray()) { _, which ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 421 | `id نامشخص` | `.setNegativeButton(R.string.common_cancel, null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 422 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 451 | `id نامشخص` | `startActivity(intent)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 479 | `id نامشخص` | `tvContent.setOnClickListener { makeCall(data.info.parent_mobile) }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 517 | `id نامشخص` | `tvContent.setOnClickListener(null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 691 | `id نامشخص` | `try { startActivity(Intent(Intent.ACTION_DIAL, Uri.parse("tel:$number"))) } catch (e: Exception) {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 700 | `id نامشخص` | `.setPositiveButton(getString(R.string.profile_delete_yes)) { _, _ -> performDelete() }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 701 | `id نامشخص` | `.setNegativeButton(getString(R.string.action_cancel), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 702 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 716 | `id نامشخص` | `Toast.makeText(this@StudentProfileActivity, res.message, Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 722 | `id نامشخص` | `finish()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 727 | `id نامشخص` | `withContext(Dispatchers.Main) { Toast.makeText(this@StudentProfileActivity, getString(R.string.profile_delete_error), Toast.LENGTH_SHORT).show() }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 745 | `id نامشخص` | `).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 764 | `id نامشخص` | `Toast.makeText(this@StudentProfileActivity, getString(R.string.profile_status_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 808 | `id نامشخص` | `.setItems(options) { _, which ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 819 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 838 | `id نامشخص` | `Toast.makeText(this, getString(R.string.profile_camera_denied), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 876 | `id نامشخص` | `Toast.makeText(this@StudentProfileActivity, getString(R.string.profile_image_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 897 | `id نامشخص` | `Toast.makeText(this@StudentProfileActivity, getString(R.string.profile_image_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 916 | `id نامشخص` | `Toast.makeText(this@StudentProfileActivity, getString(R.string.common_ok_msg, response.message), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 923 | `id نامشخص` | `Toast.makeText(this@StudentProfileActivity, getString(R.string.profile_upload_error), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 1023 | `id نامشخص` | `.setPositiveButton(getString(R.string.installment_pay_yes)) { _, _ -> performPayInstallment(item.id) }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 1024 | `id نامشخص` | `.setNegativeButton(getString(R.string.common_cancel), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 1025 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 1032 | `id نامشخص` | `Toast.makeText(this@StudentProfileActivity, getString(R.string.installment_paying), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 1038 | `id نامشخص` | `Toast.makeText(this@StudentProfileActivity, msg, Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 1047 | `id نامشخص` | `Toast.makeText(this@StudentProfileActivity, getString(R.string.common_err_with_detail, detail), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 1058 | `id نامشخص` | `.setPositiveButton(getString(R.string.installment_remind)) { _, _ -> performRemindInstallment(item.id) }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 1059 | `id نامشخص` | `.setNegativeButton(getString(R.string.common_cancel), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 1060 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 1067 | `id نامشخص` | `Toast.makeText(this@StudentProfileActivity, getString(R.string.installment_remind_sending), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 1073 | `id نامشخص` | `Toast.makeText(this@StudentProfileActivity, msg, Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 1080 | `id نامشخص` | `Toast.makeText(this@StudentProfileActivity, getString(R.string.common_err_with_detail, detail), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 1092 | `id نامشخص` | `Toast.makeText(this@StudentProfileActivity, getString(R.string.installment_loading_enrollments), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 1099 | `id نامشخص` | `Toast.makeText(this@StudentProfileActivity, getString(R.string.installment_error_no_enrollment), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 1131 | `id نامشخص` | `.setPositiveButton(getString(R.string.action_save), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 1132 | `id نامشخص` | `.setNegativeButton(getString(R.string.common_cancel), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 1134 | `id نامشخص` | `dialog.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 1135 | `id نامشخص` | `dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 1139 | `id نامشخص` | `Toast.makeText(this@StudentProfileActivity, getString(R.string.installment_error_no_enrollment), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 1140 | `id نامشخص` | `return@setOnClickListener` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 1148 | `id نامشخص` | `Toast.makeText(this@StudentProfileActivity, getString(R.string.installment_error_amount), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 1149 | `id نامشخص` | `return@setOnClickListener` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 1153 | `id نامشخص` | `return@setOnClickListener` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 1159 | `id نامشخص` | `Toast.makeText(this@StudentProfileActivity, getString(R.string.installment_error_due), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 1160 | `id نامشخص` | `return@setOnClickListener` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 1170 | `id نامشخص` | `Toast.makeText(this@StudentProfileActivity, getString(R.string.common_err_with_detail, detail), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 1180 | `id نامشخص` | `Toast.makeText(this@StudentProfileActivity, getString(R.string.installment_creating), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 1187 | `id نامشخص` | `Toast.makeText(this@StudentProfileActivity, msg, Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 1196 | `id نامشخص` | `Toast.makeText(this@StudentProfileActivity, getString(R.string.common_err_with_detail, detail), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 1245 | `id نامشخص` | `holder.btnPay.setOnClickListener { onPay(item) }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 1246 | `id نامشخص` | `holder.btnRemind.setOnClickListener { onRemind(item) }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 1270 | `id نامشخص` | `).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 1276 | `id نامشخص` | `Toast.makeText(this@StudentProfileActivity, getString(R.string.profile_portal_error), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |

## تماس‌های سرور در این فایل

| خط | فراخوانی | method/path از CSV فاز B |
|---:|---|---|
| 335 | `networkCall = { api.getFullStudentProfile(studentId) },` | `GET admin/students/{id}/full_profile, GET admin/students/{id}/full_profile` |
| 536 | `networkCall = { api.getStudentGrades(studentId) },` | `GET students/{id}/grades` |
| 625 | `val history = api.getStudentCommunicationHistory(studentId)` | `GET students/{id}/communication_history` |
| 657 | `val list = api.getTimeline(studentId)` | `GET students/{id}/timeline` |
| 711 | `val res = api.deleteStudent(studentId)` | `DELETE admin/students/{id}` |
| 739 | `val res = api.toggleSuspend(studentId)` | `POST admin/students/{id}/toggle_suspend` |
| 914 | `val response = api.uploadStudentPhoto(studentId, body)` | `POST students/{id}/upload_photo` |
| 952 | `networkCall = { api.getStudentInstallments(studentId) },` | `GET students/{id}/installments` |
| 1035 | `val res = api.payInstallment(installmentId)` | `POST finance/installments/{id}/pay` |
| 1070 | `val res = api.remindInstallment(installmentId)` | `POST finance/installments/{id}/remind` |
| 1184 | `val res = api.createInstallment(req)` | `POST finance/installments` |
| 1264 | `val res = api.sendPortalLink(studentId)` | `POST admin/students/{id}/send_portal_link` |

## داده‌های نمایشی و محاسبهٔ سمت اپ

| خط | assignment/render | منشأ قابل اثبات |
|---:|---|---|
| 252 | `rvTimeline.adapter = timelineAdapter` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 271 | `rvInstallments.adapter = installmentAdapter` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 338 | `tvName.text = data.info.name` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 339 | `tvPhone.text = data.info.student_mobile` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 355 | `.load(glideUrl)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 373 | `tvTotalDebt.text = buildTotalStatus(data.walletTotal, data.totalDebt)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 377 | `tvDebtTeacher.text = buildWalletStatus(getString(R.string.profile_wallet_teacher), data.walletTeacher, data.debtTeacher)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 381 | `tvDebtInstitute.text = buildWalletStatus(getString(R.string.profile_wallet_institute), data.walletInstitute, data.debtInstitute)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 396 | `tvContent.text = getString(R.string.common_offline_empty)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 480 | `tvContent.text = sb.toString()` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 516 | `tvContent.text = sb.toString()` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 522 | `tvContent.text = getString(R.string.profile_grades_loading)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 561 | `tvContent.text = sb.toString()` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 569 | `tvContent.text = getString(R.string.common_offline_empty)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 592 | `tvInstallmentsEmpty.text = getString(R.string.profile_inst_loading)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 611 | `tvTimelineEmpty.text = getString(R.string.timeline_loading)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 618 | `tvCommunicationEmpty.text = getString(R.string.profile_comm_loading)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 627 | `rvCommunicationHistory.adapter = CommunicationHistoryAdapter(history)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 633 | `tvCommunicationEmpty.text = getString(R.string.profile_comm_empty)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 642 | `tvCommunicationEmpty.text =` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 651 | `tvTimelineEmpty.text = getString(R.string.timeline_loading)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 661 | `tvTimelineEmpty.text = getString(R.string.timeline_empty)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 683 | `tvTimelineEmpty.text = getString(R.string.timeline_error, detail)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 936 | `tvInstallmentsEmpty.text = getString(R.string.profile_inst_loading)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 939 | `tvContent.text = getString(R.string.profile_inst_loading)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 957 | `tvInstallmentsEmpty.text = getString(R.string.installment_no_installments)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 972 | `tvInstallmentsEmpty.text = getString(R.string.common_offline_empty)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 1115 | `actvCourse.setText(courseNames[0], false)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 1119 | `actvCourse.setText(courseNames[0], false)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 1122 | `etDue.setText(JalaliUtils.todayJalaliString())` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 1225 | `holder.tvCourse.text = item.course_title` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 1226 | `holder.tvAmount.text = holder.itemView.context.getString(R.string.common_toman_format, item.amount)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 1227 | `holder.tvDue.text = holder.itemView.context.getString(R.string.installment_due, item.due_date)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 1229 | `holder.tvStatus.text = holder.itemView.context.getString(R.string.installment_paid_label)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 1232 | `holder.tvPaidAt.text = holder.itemView.context.getString(R.string.profile_inst_paidat, item.paid_at)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 1236 | `holder.tvStatus.text = if (overdue) holder.itemView.context.getString(R.string.profile_inst_overdue) else holder.itemView.context.getString(R.string.profile_inst_pending)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |

## مراجع تکمیلی

- API declarationها و type فیلدها: [`../android-api-calls.csv`](../android-api-calls.csv).
- route و handler سمت سرور: [`../server-routes.csv`](../server-routes.csv).
