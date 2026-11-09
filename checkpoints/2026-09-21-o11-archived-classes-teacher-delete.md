# O-11 — حذف معلم با کلاسِ آرشیوشده ممکن نبود و پیام «N کلاس فعال» غلط بود

- **تاریخ:** ۲۰۲۶-۰۹-۲۱ · **Branch:** `arena/01a0bf8d-kharazmiapp` · **موج:** ۳ (مورد ۱۰)
- **Base HEAD:** `fa8db9b` (O-10) · **دسته:** ادمین/کلاس‌ها · **شدت:** کم-متوسط

## ریشه
در `routers/admin.py` تابع `delete_teacher`، گارد «کلاس فعال» بدون فیلتر حذف شمرده می‌شد:

```python
active_classes = db.query(Course).filter(Course.teacher_id == teacher_id).count()
```

⇒ **هر** کلاس معلم — از جمله کلاسی که قبلاً آرشیو/حذف منطقی شده بود — «فعال» حساب می‌شد. دو پیامد:
1. معلمی که فقط کلاس آرشیوشده داشت اصلاً قابل حذف نبود (۴۰۰ نادرست)؛
2. متن خطا («این معلم N کلاس فعال دارد») عدد اشتباه نشان می‌داد.

## اعداد قبل/بعد روی کپی `/tmp/o11_demo.db` (کپی `gaj_db.db`)
| معلم | سناریو | قبل (کوئری بدون فیلتر) | بعد (کوئری با `is_deleted == False`) | پاسخ API بعد از فیکس |
|---|---|---|---|---|
| «دارای‌فعال» | ۱ کلاس فعال + ۱ آرشیو | `active_classes=2` ⇒ ۴۰۰ با «2 کلاس فعال» | `active_classes=1` | ۴۰۰ با «این معلم **1** کلاس فعال دارد.» |
| «فقط‌آرشیو» | ۱ کلاس آرشیو | `active_classes=1` ⇒ ۴۰۰ (حذف **ممکن نبود**) | `active_classes=0` | ۲۰۰ `{"message": "معلم با موفقیت حذف (آرشیو) شد"}` و `is_deleted=True` |

## فیکس
| فایل | تغییر |
|---|---|
| `routers/admin.py` (`delete_teacher`) | `Course.is_deleted == False` به کوئری `active_classes` اضافه شد (تک‌خطی، بدون تغییر سایر گاردهای حذف) |

سایر مسیرهای حذف/آرشیو کلاس (A2/A3، H10) دست‌نخورده ماند.

## تست
- **قرمز اول:** دو تست جدید در `tests/test_admin.py` پیش از فیکس ⇒ **2 failed, 7 passed**
  - `test_delete_teacher_allowed_when_all_classes_are_archived` — معلم با فقط کلاس آرشیو باید حذف شود.
  - `test_delete_teacher_message_counts_only_active_classes` — متن خطا باید «1 کلاس فعال» بگوید (و «2 کلاس فعال» نگوید).
- **پس از فیکس:** `tests/test_admin.py` ⇒ **9 passed** · کل سوئیت ⇒ **1061 passed** · md5 `gaj_db.db` بی‌تغییر
  (`f048f8d118b33c4eaa944490594121d7`).

## Commit / Push
- پیام: `fix: allow deleting a teacher whose classes are all archived (O-11)`
