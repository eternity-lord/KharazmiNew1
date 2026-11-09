# TeacherProfileActivity

- Kotlin: `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/TeacherProfileActivity.kt:50`
- layout و محل bind:
  - `R.layout.activity_teacher_profile` در `KharazmiAdmin/app/src/main/java/com/example/kharazmiadmin/TeacherProfileActivity.kt:83`؛ فایل `KharazmiAdmin/app/src/main/res/layout/activity_eacher_profile.xml:1` در صورت وجود.

> این سند از جست‌وجوی محتوای source ساخته شده است. هر موردی که source آن را صریح نکرده با «نامشخص» آمده و حدس زده نشده است. Android compile اجرا نشده است.

## عناصر تعاملی، API و navigation

| خط | id صریح نزدیک handler | سطر handler/transition | route قابل اتصال |
|---:|---|---|---|
| 98 | `btnCallTeacher` | `findViewById<MaterialButton>(R.id.btnCallTeacher).setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 101 | `id نامشخص` | `startActivity(intent)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 106 | `btnSuspendTeacher` | `findViewById<MaterialButton>(R.id.btnSuspendTeacher).setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 111 | `btnDeleteTeacher` | `findViewById<MaterialButton>(R.id.btnDeleteTeacher).setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 116 | `fabEditTeacher` | `findViewById<FloatingActionButton>(R.id.fabEditTeacher).setOnClickListener {` | Intent → EditTeacherActivity |
| 119 | `id نامشخص` | `startActivity(intent)` | Intent → EditTeacherActivity |
| 123 | `id نامشخص` | `btnSubmitSettlement.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 125 | `id نامشخص` | `Toast.makeText(this, getString(R.string.tprof_no_unsettled), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 126 | `id نامشخص` | `return@setOnClickListener` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 137 | `id نامشخص` | `startActivity(intent)` | Intent → ClassDetailActivity |
| 358 | `id نامشخص` | `Toast.makeText(this@TeacherProfileActivity, getString(R.string.common_offline_empty), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 438 | `id نامشخص` | `.setPositiveButton("ثبت برگشت") { _, _ ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 451 | `id نامشخص` | `Toast.makeText(this@TeacherProfileActivity, settlementError("برگشت تسویه", error), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 456 | `id نامشخص` | `.setNegativeButton("انصراف", null).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 463 | `id نامشخص` | `.setPositiveButton("ثبت تعدیل") { _, _ ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 477 | `id نامشخص` | `Toast.makeText(this@TeacherProfileActivity, settlementError("تعدیل تسویه", error), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 481 | `id نامشخص` | `}.setNegativeButton("انصراف", null).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 491 | `id نامشخص` | `.setPositiveButton(getString(R.string.tprof_settle_yes)) { _, _ ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 494 | `id نامشخص` | `.setNegativeButton(getString(R.string.common_cancel), null)` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 495 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 560 | `btnClose` | `btnClose.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 563 | `id نامشخص` | `dialog.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 571 | `id نامشخص` | `Toast.makeText(this@TeacherProfileActivity, getString(R.string.tprof_settle_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 615 | `id نامشخص` | `Toast.makeText(this@TeacherProfileActivity, response.message, Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 624 | `id نامشخص` | `Toast.makeText(this@TeacherProfileActivity, getString(R.string.tprof_suspend_error), Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 636 | `id نامشخص` | `.setPositiveButton(getString(R.string.common_delete_yes)) { dialog, _ ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 640 | `id نامشخص` | `.setNegativeButton(getString(R.string.common_cancel)) { dialog, _ ->` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 643 | `id نامشخص` | `.show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 655 | `id نامشخص` | `Toast.makeText(this@TeacherProfileActivity, response.message, Toast.LENGTH_SHORT).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 660 | `id نامشخص` | `finish()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 664 | `id نامشخص` | `Toast.makeText(this@TeacherProfileActivity, getString(R.string.tprof_del_error, e.message), Toast.LENGTH_LONG).show()` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 717 | `id نامشخص` | `holder.itemView.setOnClickListener {` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 795 | `id نامشخص` | `holder.btnReverseSettlement.setOnClickListener { onReverse(item) }` | route از context همین سطر/سطرهای مجاور مشخص نیست |
| 796 | `id نامشخص` | `holder.btnEditSettlement.setOnClickListener { onEdit(item) }` | route از context همین سطر/سطرهای مجاور مشخص نیست |

## تماس‌های سرور در این فایل

| خط | فراخوانی | method/path از CSV فاز B |
|---:|---|---|
| 238 | `val history = api.getTeacherCommunicationHistory(teacherId)` | `GET teachers/{id}/communication_history` |
| 277 | `networkCall = { profileApi.getFullTeacherProfile(teacherId) },` | `GET teachers/{id}/full_profile` |
| 385 | `networkCall = { api.getPendingSettlement(teacherId) },` | `GET teachers/{id}/pending_settlement` |
| 410 | `networkCall = { api.getSettlementHistory(teacherId) },` | `GET teachers/{id}/settlement_history` |
| 508 | `val res = api.settleTeacherSessions(teacherId, SettleRequest(pendingSessionIds))` | `POST teachers/{id}/settle` |
| 585 | `val collab = api.getTeacherCollaborationSummary(teacherId)` | `GET teachers/{id}/collaboration_summary` |
| 614 | `val response = withContext(Dispatchers.IO) { api.suspendTeacher(teacherId) }` | `POST /admin/teachers/{teacher_id}/suspend` |
| 654 | `val response = withContext(Dispatchers.IO) { api.deleteTeacher(teacherId) }` | `DELETE /admin/teachers/{teacher_id}` |

## داده‌های نمایشی و محاسبهٔ سمت اپ

| خط | assignment/render | منشأ قابل اثبات |
|---:|---|---|
| 139 | `rvClasses.adapter = classAdapter` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 231 | `tvCommunicationEmpty.text = getString(R.string.profile_comm_loading)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 240 | `rvCommunicationHistory.adapter = CommunicationHistoryAdapter(history)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 246 | `tvCommunicationEmpty.text = getString(R.string.profile_comm_empty)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 255 | `tvCommunicationEmpty.text =` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 282 | `findViewById<TextView>(R.id.tvTeacherName).text = "${data.info.name ?: ""}$codeStr"` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 283 | `findViewById<TextView>(R.id.tvTeacherPhone).text = data.info.mobile ?: ""` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 301 | `.load(glideUrl)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 312 | `findViewById<TextView>(R.id.tvRevenue).text = String.format(java.util.Locale.US, "%,d", data.total_revenue)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 313 | `findViewById<TextView>(R.id.tvStudentCount).text = data.total_students.toString()` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 314 | `findViewById<TextView>(R.id.tvClassCount).text = data.active_classes_count.toString()` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 322 | `tvCollabAvgDelay.text = getString(R.string.tprof_delay, collab.averageDelayMinutes, collab.delaySamplesCount)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 323 | `tvCollabLiveCount.text = getString(R.string.tprof_live, collab.liveSessionsLast30Days)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 324 | `tvCollabSettlements.text = getString(R.string.tprof_settlements, collab.totalSettlementsCount, String.format(Locale("en", "US"), "%,d", collab.totalSettledAmount))` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 325 | `tvCollabAutoEnded.text = getString(R.string.tprof_autoend, collab.autoEndedSessionsCount, collab.autoEndedLast30DaysCount)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 326 | `tvCollabPeriod.text = getString(R.string.tprof_period, collab.periodStart, collab.periodEnd)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 387 | `tvPendingSettlementSum.text = getString(R.string.tprof_pending, String.format(Locale("en", "US"), "%,d", data.total_amount))` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 390 | `rvPendingSettlementSessions.adapter = PendingSessionsAdapter(data.pending_sessions)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 399 | `tvPendingSettlementSum.text = getString(R.string.tprof_zero)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 401 | `rvPendingSettlementSessions.adapter = null` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 412 | `rvSettlementHistory.adapter = SettlementHistoryAdapter(history,` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 417 | `rvSettlementHistory.adapter = null` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 545 | `dialogView.findViewById<TextView>(R.id.tvSuccessMessage).text =` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 559 | `btnClose.text = getString(R.string.common_ok)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 588 | `tvCollabAvgDelay.text = getString(R.string.tprof_delay, collab.averageDelayMinutes, collab.delaySamplesCount)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 589 | `tvCollabLiveCount.text = getString(R.string.tprof_live, collab.liveSessionsLast30Days)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 590 | `tvCollabSettlements.text = getString(R.string.tprof_settlements, collab.totalSettlementsCount, String.format(Locale("en", "US"), "%,d", collab.totalSettledAmount))` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 591 | `tvCollabAutoEnded.text = getString(R.string.tprof_autoend, collab.autoEndedSessionsCount, collab.autoEndedLast30DaysCount)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 592 | `tvCollabPeriod.text = getString(R.string.tprof_period, collab.periodStart, collab.periodEnd)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 698 | `holder.tvClassName.text = classItem.title ?: ""` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 699 | `holder.tvClassCode.text = holder.itemView.context.getString(R.string.tprof_class_code, classItem.code ?: "")` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 700 | `holder.tvClassDetails.text = classItem.grade_level ?: ""` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 704 | `holder.tvClassStatus.text = holder.itemView.context.getString(R.string.tprof_suspended)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 708 | `holder.tvClassStatus.text = holder.itemView.context.getString(R.string.tprof_pending2)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 712 | `holder.tvClassStatus.text = holder.itemView.context.getString(R.string.tprof_active)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 744 | `holder.tvClassTitle.text = holder.itemView.context.getString(R.string.tprof_row, item.class_title ?: "", codeStr, item.present_count)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 748 | `holder.tvSessionDate.text = if (sessionDate != null) {` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 754 | `holder.tvSessionAmount.text = holder.itemView.context.getString(R.string.portal_money, String.format(java.util.Locale.US, "%,d", amt))` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 788 | `holder.tvSettledAmount.text = holder.itemView.context.getString(R.string.portal_money, String.format(java.util.Locale.US, "%,d", amt))` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 789 | `holder.tvSettlementDocument.text = "سند تسویه #${item.id} \| ${if (item.is_reversed) "برگشت‌خورده" else "فعال"}" +` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 791 | `holder.tvSettledDate.text = holder.itemView.context.getString(R.string.tprof_settled_date, item.settled_at ?: "")` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |
| 792 | `holder.tvSessionCount.text = holder.itemView.context.getString(R.string.tprof_sessions, item.session_count)` | data class/JSON طبق declaration متناظر در `../android-api-calls.csv`؛ منشأ DB در route سرور متناظر `../server-routes.csv` |

## مراجع تکمیلی

- API declarationها و type فیلدها: [`../android-api-calls.csv`](../android-api-calls.csv).
- route و handler سمت سرور: [`../server-routes.csv`](../server-routes.csv).
