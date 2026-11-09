# نوبت جاری — راستی‌آزمایی برنچ نشسته و اثبات دسترسی نوشتن + اجرای کامل تست‌ها

- **تاریخ:** ۲۰۲۶-۰۹-۲۲ · **Branch:** `arena/01a0c867-kharazmiapp`
- **Base HEAD:** `3d80c3789209a3e4d32deaf3f46638cdaba38e18` — **دقیقاً همان نوکِ `arena/01a0bf8d-kharazmiapp`** (برنچ اصلی کاربر)
- **درخواست کاربر:** «کدهای برنچ اصلی را کامل کپی کن؛ اگر نمی‌توانی روی این برنچ کامیت/پوش کنی، برنچ دیگری بساز؛ بعد تست کن.»
- **دامنه:** **صفر تغییر در کد برنامه** (سرور/اندروید). فقط راستی‌آزمایی + یک تغییر در workflow CI.
- **وضعیت:** دسترسی نوشتن اثبات شد · محتوا بایت‌به‌بایت یکسان با برنچ کاربر · **۱۰۷۷ passed** محلی و **CI سبز**.

---

## ۱) چرا «کپی کردن» لازم نبود

برنچ این نشست از همان کامیتِ نوک برنچ کاربر ساخته شده است، نه از `main`:

| بررسی | نتیجه |
|---|---|
| `git ls-remote origin refs/heads/arena/01a0bf8d-kharazmiapp` | `3d80c37…` |
| `git rev-parse HEAD` (پایهٔ نشست) | `3d80c37…` (یکسان) |
| Tree hash هر دو برنچ | `32871391eea5a1900ff044e9bebed0bfbd54a32f` (یکسان) |
| `git diff --exit-code origin/arena/01a0bf8d-kharazmiapp HEAD` | بدون خروجی ⇒ **۰ اختلاف** |
| مقایسهٔ هش تک‌تک فایل‌ها (`git ls-tree -r` هر دو) | **۰ اختلاف** از ۶۳۳ فایل |
| `git rev-list --left-right --count` | `0  0` |

> `origin/main` (`4e44c87`) تاریخچهٔ **جدا و قدیمی** است (بدون merge-base با برنچ کاربر، شامل
> `kharazmizip.zip`، بدون `pytest.ini` و CI). طبق قانون پروژه **دست‌نخورده** ماند؛ PR #1 هم همین‌طور.
> برنچ `arena/01a0b352-kharazmiapp` هم ۱۶۹ فایل عقب‌تر است و لمس نشد.

موجودی تأییدشده: ۶۳۳ فایل = ۳۱۰ `KharazmiAdmin` (۸۳ Kotlin · ۹۶ layout) + ۱۴۰ `Kharazmi_Server`
(۲۵ router · ۶۶ فایل تست در `tests/`) + ۱۷۹ چک‌پوینت + `README.md` + `THIRD_PARTY_NOTICES.md`
+ `pytest.ini` + `.github/workflows/tests.yml`.

## ۲) اثبات دسترسی نوشتن (کامیت + پوش واقعی)

| قدم | نتیجه |
|---|---|
| ساخت فایل `WRITE_ACCESS_TEST.md` + کامیت | ✅ `8116ea9` |
| `git push origin arena/01a0c867-kharazmiapp` | ✅ `3d80c37..8116ea9` (بدون خطای احراز هویت) |
| حذف همان فایل با کامیت دوم | ✅ `5803154` ⇒ tree دوباره **یکسان** با برنچ کاربر (`3287139…`) |
| تغییر workflow و پوش سوم | ✅ `09af2a8` |

**نتیجه:** نوشتن/کامیت/پوش روی برنچ نشست **بدون مشکل** کار می‌کند ⇒ نیازی به ساخت برنچ دیگر نبود.
(این نشست به برنچ `arena/01a0c867-kharazmiapp` قفل است؛ ساخت/پوش برنچ با نام دیگر مجاز نیست —
اگر نام دیگری لازم است، از GitHub UI از همین برنچ branch بزنید: محتوایش یکسان است.)

## ۳) تنها تغییر این نوبت: تریگر CI

`.github/workflows/tests.yml` فقط روی `main` و `arena/01a0bf8d-kharazmiapp` تریگر می‌شد، پس pushهای
این برنچ CI را اجرا نمی‌کردند و `workflow_dispatch` هم با توکن این نشست **۴۰۳** داد
(`Resource not accessible by integration` ⇒ اکشنز write ندارد). راه‌حل: افزودن نام این برنچ به فهرست
`on.push.branches` (بدون حذف هیچ تریگر قبلی، بدون تغییر هیچ step).

## ۴) نتیجهٔ تست‌ها

| مسیر | نتیجه |
|---|---|
| محلی (venv تازه، Python 3.11.2، DB موقت `/tmp/kharazmi_local_test.db`) | ✅ **1077 passed** در ۱۰۹ ثانیه (`-p no:randomly`) |
| CI روی همین برنچ — run [`35710062658`](https://github.com/eternity-lord/KharazmiApp/actions/runs/35710062658) | ✅ **success** در ۱m58s |
| step «Run full suite from repository root» | ✅ |
| step «cwd-independence guard (B1)» | ✅ |
| step «Guard - real institute database untouched» | ✅ |
| md5 `gaj_db.db` قبل و بعد (محلی) | `f048f8d118b33c4eaa944490594121d7` — **بی‌تغییر** (قانون طلایی رعایت شد) |

دستور اجرا:
```bash
DATABASE_URL=sqlite:////tmp/<n>.db JWT_SECRET_KEY=<hex> \
  .venv/bin/python -m pytest Kharazmi_Server/tests -q -p no:randomly
```

۳۴ warning موجود (همهٔ `PydanticDeprecatedSince20` برای `.dict()` در `classes.py:105`،
`teachers.py:84/511`، `students.py:783`) از قبل بودند و در این نوبت **دست نخوردند** — خارج از دامنه.

## ۵) چه چیزی تست نشد / محدودیت‌ها

1. **اندروید کامپایل نشد** (Gradle/JDK/Android SDK در این محیط نیست) — مثل تمام نوبت‌های قبل؛
   تغییرات سمت Kotlin/layout فقط ایستا بررسی می‌شوند و تأیید نهایی با نصب روی دستگاه کاربر است.
2. هیچ نوشتنی روی **دیتابیس واقعی** آموزشگاه انجام نشد؛ همه‌چیز روی DB موقت.
3. `workflow_dispatch` با توکن این نشست کار نمی‌کند (۴۰۳)؛ CI فقط از راه push تریگر شد.
4. موارد بازِ مستندشده در `2026-09-21-final-phase-report.md` (O-02 پوش/FCM، O-12، O-14، O-19)
   و یافته‌های ب-۱…ب-۱۰ **دست‌نخورده** باقی‌اند.

## ۶) قدم بعدی

کاربر یا برنچ `arena/01a0c867-kharazmiapp` را به‌عنوان برنچ کاری ادامه می‌دهد (محتوا = برنچ اصلی)
یا از GitHub UI برنچ هم‌نام دیگری از آن می‌سازد. سپس یکی از موارد باز (اولویت: O-02 پوش مرده،
ب-۱ ورود دوم معلم، ب-۵ دسترسی دانش‌آموز حذف‌شده) با چرخهٔ قرمز → سبز انجام می‌شود.
