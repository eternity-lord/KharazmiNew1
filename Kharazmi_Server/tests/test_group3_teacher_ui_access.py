# test_group3_teacher_ui_access.py
# ═══════════════════════════════════════════════════════════════════════════════
# گروه ۳ — دسترسی نادرست معلم در اپ ادمین (آیتم‌های ۱۰ تا ۱۵)
#
#   ۱۰) پاپ‌آپ بعد از تسویه: «ثبت مجدد برای دانش‌آموز دیگر» فقط در مسیر ثبت حوالهٔ
#       دانش‌آموز بماند و در تسویهٔ حساب معلم (پروفایل عملکرد معلم) حذف شود
#   ۱۱) داشبورد معلم: دکمهٔ «ثبت حواله» حذف
#   ۱۲) بنر کلاس در پنل معلم: تعلیق + ثبت حواله مخفی
#   ۱۳) صفحهٔ کلاس در پنل معلم: «امور مدیریتی» مخفی، فقط اصلاح اطلاعات + حذف کلاس
#   ۱۴) تاریخچهٔ جلسات معلم: امور مدیریتی/تعلیق/ثبت حواله مخفی
#   ۱۵) پاپ‌آپ نهایی ثبت کلاس برای معلم: دکمهٔ «رفتن به کلاس‌های منتظر تأیید» حذف
#
# چرا تست ایستا (اسکن متن کد کاتلین)؟
#   طبق قانون پروژه در این سندباکس Gradle/JDK/Android SDK وجود ندارد و اندروید هرگز
#   کامپایل نمی‌شود ⇒ قرارداد UI با همان الگوی موجودِ پروژه قفل می‌شود:
#   `test_class_restore_metadata.py::test_13_android_client_surfaces_restore_warnings`
#   و `test_android_resources_static.py` (گاردهای ایستا روی res/ و R.string/R.id).
#   اینجا هم «چه چیزی باید مخفی/حذف شود» و «چه چیزی باید سر جایش بماند» با assertRegex
#   روی تابعِ مربوطه قفل می‌شود تا رگرسیون (پنهان‌شدن دکمه در مسیر ادمین) دیده شود.
#
# اجرا (DB موقت — هرگز gaj_db.db واقعی):
#   DATABASE_URL=sqlite:////tmp/g3.db JWT_SECRET_KEY=test \
#     python3 -m pytest Kharazmi_Server/tests/test_group3_teacher_ui_access.py -q
# ═══════════════════════════════════════════════════════════════════════════════
import os
import re
import unittest

SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(SERVER_DIR)
KT_DIR = os.path.join(REPO_ROOT, "KharazmiAdmin", "app", "src", "main", "java",
                      "com", "example", "kharazmiadmin")
RES_DIR = os.path.join(REPO_ROOT, "KharazmiAdmin", "app", "src", "main", "res")


def kt(name: str) -> str:
    path = os.path.join(KT_DIR, name)
    assert os.path.exists(path), f"فایل کاتلین پیدا نشد: {path}"
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def layout(name: str) -> str:
    path = os.path.join(RES_DIR, "layout", name)
    assert os.path.exists(path), f"لی‌اوت پیدا نشد: {path}"
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def kt_strings() -> str:
    path = os.path.join(RES_DIR, "values", "strings.xml")
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def strip_comments(source: str) -> str:
    """کامنت‌ها را حذف می‌کند تا گارد روی کد واقعی باشد، نه توضیحات (الگوی test_android_resources_static)."""
    source = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), source, flags=re.S)
    return re.sub(r"^\s*//.*$", "", source, flags=re.M)


def function_body(source: str, name: str) -> str:
    """بدنهٔ یک تابع کاتلین تا شروع تابع هم‌سطح بعدی (برای گاردِ «فقط در این مسیر»)."""
    code = strip_comments(source)
    match = re.search(r"\n\s*(?:(?:private|internal|public|override|open|suspend)\s+)*fun\s+"
                      + re.escape(name) + r"\s*\(", code)
    assert match, f"تابع {name} در سورس پیدا نشد"
    rest = code[match.end():]
    nxt = re.search(r"\n\s{0,4}(?:private |internal |public |override )*fun\s+\w+", rest)
    return rest[:nxt.start()] if nxt else rest


GONE = r"R\.id\.{btn}\)\.visibility\s*=\s*View\.GONE"


class TestItem10SettlementPopupButton(unittest.TestCase):
    """آیتم ۱۰ — «ثبت مجدد برای دانش‌آموز دیگر» در پاپ‌آپ تسویهٔ معلم.

    ریشه (قبل از فیکس): `TeacherProfileActivity.performSettlement()` همان لی‌اوت
    `dialog_remittance_success` را inflate می‌کند و فقط `btnPrintRemittance` و
    `btnSaveAsPdf` را GONE می‌کرد ⇒ دکمهٔ «ثبت مجدد برای دانش‌آموز دیگر» در پاپ‌آپ
    تسویهٔ **معلم** دیده می‌شد (و چون اینجا listener ندارد، کلیکش هیچ کاری نمی‌کرد).
    الگوی درستِ موجود: `AttendanceActivity` همان دکمه را GONE می‌کند.
    """

    def test_10a_the_button_text_is_the_one_the_owner_sees(self):
        """اطمینان از اینکه سراغ همان دکمه رفته‌ایم (متن لی‌اوت، نه یک دکمهٔ دیگر)."""
        xml = layout("dialog_remittance_success.xml")
        block = xml[xml.index('android:id="@+id/btnRegisterAgain"'):]
        self.assertIn("ثبت مجدد برای دانش‌آموز دیگر", block[:400], block[:400])

    def test_10b_teacher_settlement_popup_hides_register_again(self):
        body = function_body(kt("TeacherProfileActivity.kt"), "performSettlement")
        self.assertIn("dialog_remittance_success", body,
                      "مسیر تسویهٔ معلم همان پاپ‌آپ حواله را inflate می‌کند")
        self.assertRegex(body, GONE.format(btn="btnRegisterAgain"),
                         "دکمهٔ «ثبت مجدد برای دانش‌آموز دیگر» باید در پاپ‌آپ تسویهٔ معلم پنهان شود")

    def test_10c_student_remittance_popup_keeps_the_button(self):
        """مسیر ثبت حوالهٔ دانش‌آموز (InvoiceActivity) باید دکمه را نگه دارد و کلیک‌پذیر کند."""
        src = strip_comments(kt("InvoiceActivity.kt"))
        self.assertIn("R.id.btnRegisterAgain", src)
        self.assertIn("btnRegisterAgain.setOnClickListener", src,
                      "در مسیر دانش‌آموز دکمه باید فعال بماند")
        self.assertNotRegex(src, GONE.format(btn="btnRegisterAgain"),
                            "دکمه در صفحهٔ ثبت حوالهٔ دانش‌آموز نباید پنهان شود")

    def test_10d_attendance_popup_still_hides_it(self):
        """الگوی موجود (جلسه/حضوروغیاب) نباید رگرسیون کند."""
        src = strip_comments(kt("AttendanceActivity.kt"))
        self.assertRegex(src, GONE.format(btn="btnRegisterAgain"))


class TestItem11TeacherDashboardInvoiceButton(unittest.TestCase):
    """آیتم ۱۱ — حذف «ثبت حواله» از داشبورد معلم.

    ریشه: کارت `cardFastInvoice` هنوز در layout وجود دارد، اما ثبت حواله/وصول پول
    کار ادمین/منشی است و نباید در پنل معلم دیده شود. رفتار درست فعلی با همان الگوی
    موجود پروژه پیاده شده است: `UserCreds` → `USER_SUB_ROLE` و گارد `isAdminUser`؛
    غیرادمین کارت را نمی‌بیند و listener فقط در شاخهٔ ادمین نصب می‌شود.
    """

    def test_11a_fast_invoice_card_is_role_gated_and_hidden(self):
        body = function_body(kt("TeacherDashboardActivity.kt"), "onCreate")
        self.assertIn("R.id.cardFastInvoice", body, "کارت ثبت حواله در همین صفحه است")
        # چک نقش موجود پروژه خوانده می‌شود (نه یک سازوکار جدید)
        self.assertRegex(body, r'getSharedPreferences\("UserCreds"')
        self.assertRegex(body, r'getString\("USER_SUB_ROLE",\s*"admin"\)')
        gate = body[body.index("USER_SUB_ROLE"):]
        self.assertRegex(
            gate,
            r'isAdminUser\s*=\s*subRole\s*==\s*"admin"\s*&&\s*userRole\s*!=\s*"teacher"',
            "گارد باید ادمین را از معلم تشخیص دهد",
        )
        self.assertRegex(
            gate,
            r"cardFastInvoice\.visibility\s*=\s*(android\.view\.)?View\.GONE",
            "کارت ثبت حواله باید برای معلم پنهان شود",
        )

    def test_11b_the_invoice_shortcut_only_stays_for_admin(self):
        """listener باید فقط داخل شاخهٔ ادمین باشد و برای معلم نصب نشود."""
        body = function_body(kt("TeacherDashboardActivity.kt"), "onCreate")
        gate = body[body.index("USER_SUB_ROLE"):]
        self.assertRegex(
            gate,
            r"(?s)if\s*\(!isAdminUser\)\s*\{.*?cardFastInvoice\.visibility\s*=\s*(?:android\.view\.)?View\.GONE.*?\}\s*else\s*\{.*?cardFastInvoice\.setOnClickListener",
            "listener ثبت حواله باید فقط در شاخهٔ ادمین باشد",
        )

    def test_11c_other_teacher_dashboard_shortcuts_are_untouched(self):
        """فقط «ثبت حواله» حذف می‌شود؛ بقیهٔ میان‌برهای پنل معلم سر جایشان می‌مانند."""
        body = function_body(kt("TeacherDashboardActivity.kt"), "onCreate")
        for card in ("cardRegisterStudent", "cardRegisterClass", "cardAttendance",
                     "cardIncompleteClasses", "cardReports"):
            self.assertIn(f"R.id.{card}", body, f"میان‌بر {card} نباید حذف شود")
            self.assertRegex(body, r"R\.id\." + card + r"\)\.setOnClickListener",
                             f"listener {card} باید سر جایش بماند")


class TestItem12TeacherClassBannerButtons(unittest.TestCase):
    """آیتم ۱۲ — مخفی‌شدن «تعلیق» و «ثبت حواله» روی بنر کلاس‌ها در پنل معلم.

    ریشه: `item_class_row.xml` دو دکمهٔ `btnSuspend` (تعلیق) و `btnRegisterInvoice`
    (ثبت حواله) را **بدون `android:visibility`** یعنی به‌صورت پیش‌فرض نمایان دارد و
    همین layout مشترک هم در `ClassManagementActivity` (ادمین) و هم در آداپتر
    `TeacherClassAdapter` داخل `TeacherDashboardActivity` (پنل معلم) inflate می‌شود.
    سمت ادمین این دو را مدیریت می‌کند (`holder.btnSuspend.visibility =
    if (isAdminUser) View.VISIBLE else View.GONE` و listener ثبت حواله)، ولی آداپتر
    معلم هرگز به آن‌ها دست نمی‌زد ⇒ در پنل معلم دو دکمهٔ نمایانِ **بی‌عملکرد**
    روی هر بنر کلاس می‌نشست.

    چون layout مشترک است، تغییر باید سمت آداپتر معلم باشد (نه خود layout)، و با همان
    چک نقش موجود (`USER_SUB_ROLE`) — همان الگوی `isAdminUser` در ClassManagementActivity.
    """

    def test_12a_both_banner_buttons_are_hidden_for_teachers(self):
        src = kt("TeacherDashboardActivity.kt")
        body = function_body(src, "onBindViewHolder")
        for btn in ("btnSuspend", "btnRegisterInvoice"):
            self.assertIn(f"R.id.{btn}", src, f"آداپتر معلم باید {btn} را پیدا کند")
            self.assertRegex(body,
                             rf"{btn}\.visibility\s*=\s*if\s*\(isAdminUser\)\s*(android\.view\.)?View\.VISIBLE\s*else\s*(android\.view\.)?View\.GONE",
                             f"{btn} باید با گارد isAdminUser روی بنر معلم پنهان شود")

    def test_12b_the_role_flag_reaches_the_adapter(self):
        """پرچم نقش از Activity (همان `USER_SUB_ROLE`) به آداپتر می‌رسد."""
        src = strip_comments(kt("TeacherDashboardActivity.kt"))
        self.assertRegex(src, r"class TeacherClassAdapter\([\s\S]{0,200}?isAdminUser\s*:\s*Boolean",
                         "آداپتر باید پرچم isAdminUser را بگیرد")
        # lambda انتهایی باید به onClick بخورد ⇒ پرچم نقش نباید آخرین پارامتر باشد
        head = re.search(r"class TeacherClassAdapter\([\s\S]*?\n\) :", src).group(0)
        self.assertLess(head.index("isAdminUser"), head.index("onClick"),
                        "onClick باید آخرین پارامتر بماند (lambda انتهاییِ محل ساخت)")
        self.assertRegex(src, r"TeacherClassAdapter\([^\n]*isAdminUser",
                         "محل ساخت آداپتر باید پرچم را پاس بدهد")
        self.assertRegex(src, r"isAdminUser\s*=\s*subRole\s*==\s*\"admin\"",
                         "پرچم باید از همان USER_SUB_ROLE موجود ساخته شود")

    def test_12c_admin_side_is_untouched(self):
        """layout مشترک و گارد ادمین در ClassManagementActivity دست‌نخورده می‌ماند."""
        row = layout("item_class_row.xml")
        self.assertIn('@+id/btnSuspend', row)
        self.assertIn('@+id/btnRegisterInvoice', row)
        cm = strip_comments(kt("ClassManagementActivity.kt"))
        self.assertRegex(cm, r"btnSuspend\.visibility\s*=\s*if\s*\(isAdminUser\)\s*View\.VISIBLE\s*else\s*View\.GONE")
        self.assertRegex(cm, r"btnRegisterInvoice\.setOnClickListener")


class TestItem13TeacherClassPageAdminAffairs(unittest.TestCase):
    """آیتم ۱۳ — صفحهٔ کلاس در پنل معلم: «امور مدیریتی» مخفی، فقط اصلاح اطلاعات + حذف کلاس.

    صفحهٔ کلاس = `ClassDetailActivity` (از بنر کلاس‌های تأییدشدهٔ داشبورد معلم باز
    می‌شود). بخش «امور مدیریتی و تنظیمات دوره» در `activity_class_detail.xml` سه دکمه
    دارد: `btnEditClassInfoAction` (اصلاح اطلاعات)، `btnSuspendAction` (تعلیق کلاس) و
    `btnDeleteClassAction` (حذف کلاس). تنها کار **مدیریتی/ادمینی** این بخش «تعلیق» است
    (`suspendClass()` مستقیم به `POST classes/{id}/suspend` می‌زند) و هیچ چک نقشی هم
    روی دکمه‌ها نبود ⇒ معلم دکمهٔ تعلیق را فعال می‌دید.
    حذف کلاس برای غیر ادمین از قبل مسیر درست را می‌رود (`showDeleteClassDialog` همان
    `USER_SUB_ROLE` را می‌خواند و به‌جای حذف، `requestDeleteClass` صدا می‌زند) ⇒ باید
    سر جایش بماند؛ اصلاح اطلاعات هم همین‌طور.
    """

    def test_13a_suspend_action_is_hidden_and_ungated_for_teachers(self):
        src = kt("ClassDetailActivity.kt")
        body = function_body(src, "onCreate")
        # همان چک نقش موجود پروژه خوانده می‌شود
        self.assertRegex(body, r'getSharedPreferences\("UserCreds"')
        self.assertRegex(body, r'getString\("USER_SUB_ROLE",\s*"admin"\)')
        gate = body[body.index("USER_SUB_ROLE"):]
        self.assertRegex(gate, r"R\.id\.btnSuspendAction\)")
        self.assertRegex(gate, r"btnSuspendAction\.visibility\s*=\s*View\.GONE",
                         "دکمهٔ تعلیق باید برای معلم پنهان شود")
        # listener فقط در شاخهٔ ادمین (دکمهٔ پنهانِ کلیک‌پذیر = راه فرار)
        self.assertRegex(gate, r"btnSuspendAction\.setOnClickListener")
        self.assertLess(gate.index("btnSuspendAction.setOnClickListener"),
                        gate.index("btnSuspendAction.visibility"))

    def test_13b_edit_info_and_delete_stay_for_teachers(self):
        body = function_body(kt("ClassDetailActivity.kt"), "onCreate")
        for btn in ("btnEditClassInfoAction", "btnDeleteClassAction"):
            self.assertRegex(body, r"R\.id\." + btn + r"\)\.setOnClickListener",
                             f"{btn} باید برای معلم هم فعال بماند")
            self.assertNotRegex(body, re.compile(btn + r"[^\n]{0,120}?View\.GONE"),
                                f"{btn} نباید در پنل معلم پنهان شود")

    def test_13c_delete_for_non_admin_is_still_a_request_not_a_delete(self):
        """مسیر موجودِ «درخواست حذف» برای غیر ادمین دست‌نخورده می‌ماند."""
        src = strip_comments(kt("ClassDetailActivity.kt"))
        self.assertRegex(src, r'val subRole = prefs\.getString\("USER_SUB_ROLE", "admin"\)')
        self.assertRegex(src, r"api\.requestDeleteClass\(classId, DeleteClassRequest\(forgive\)\)")
        self.assertRegex(src, r"api\.deleteClass\(classId, forgive\)")

    def test_13d_layout_and_endpoints_untouched(self):
        """layout مشترک و endpointها دست نمی‌خورند (فقط UI سمت معلم)."""
        detail = layout("activity_class_detail.xml")
        for btn in ("btnEditClassInfoAction", "btnSuspendAction", "btnDeleteClassAction"):
            self.assertIn("@+id/" + btn, detail)
        self.assertIn("امور مدیریتی و تنظیمات دوره", detail)
        self.assertEqual(strip_comments(kt("ClassDetailActivity.kt")).count("suspendClass()"), 2,
                         "فقط یک فراخوانی suspendClass() از دکمه می‌آید (تعریف + کلیک ادمین)")


class TestItem15TeacherClassRegistrationPopup(unittest.TestCase):
    """آیتم ۱۵ — پاپ‌آپ نهایی ثبت کلاس برای معلم: «رفتن به کلاس‌های منتظر تایید» حذف.

    مسیر: پنل معلم → بنر کلاسِ در انتظار تأیید (یا «کلاس‌های ناقص») → `ClassSetupActivity`
    → «ثبت نهایی و اتمام کلاس» → `showClassSummaryPage()`. بعد از «ارسال برای تأیید»،
    دیالوگِ `csetup_sent_msg` **سه** دکمه دارد: «باشه» (positive) و
    «رفتن به کلاس‌های منتظر تایید» (neutral) که `PendingClassesActivity` را باز می‌کند —
    صفحه‌ای که صفِ **تأیید ادمین** است (رد/تایید کلاس‌ها) و معلم کارِ آن‌جا ندارد.
    چک نقش، همان الگوی موجودِ خودِ این فایل است (UserCreds → USER_SUB_ROLE؛ در
    آداپتر دانش‌آموزانِ همین Activity برای منشی دکمهٔ حذف را GONE می‌کند).
    """

    def test_15a_pending_classes_button_only_exists_for_admin(self):
        body = function_body(kt("ClassSetupActivity.kt"), "showClassSummaryPage")
        self.assertRegex(body, r'getSharedPreferences\("UserCreds"')
        self.assertRegex(body, r'getString\("USER_SUB_ROLE",\s*"admin"\)')
        gate = body[body.index("USER_SUB_ROLE"):]
        self.assertRegex(gate, r'if\s*\(subRole\s*==\s*"admin"\)')
        self.assertRegex(gate, r"setNeutralButton\(getString\(R\.string\.csetup_sent_go\)\)")
        self.assertRegex(gate, r"PendingClassesActivity::class\.java")
        # هر دو باید **بعد از** گارد نقش بیایند (قبلاً بی‌قیدوشرط ساخته می‌شد)
        self.assertGreater(gate.index("setNeutralButton"), gate.index('subRole == "admin"'))
        self.assertGreater(gate.index("PendingClassesActivity::class.java"), gate.index('subRole == "admin"'))

    def test_15b_the_teacher_still_gets_the_confirmation_dialog(self):
        """پیام «به مدیر اطلاع بده» و دکمهٔ «باشه» برای معلم سر جایشان می‌مانند."""
        body = function_body(kt("ClassSetupActivity.kt"), "showClassSummaryPage")
        gate = body[body.index("USER_SUB_ROLE"):]
        self.assertLess(gate.index("csetup_sent_title"), gate.index('subRole == "admin"'),
                        "دیالوگ باید برای همه ساخته شود؛ فقط دکمهٔ میانی ادمینی است")
        self.assertLess(gate.index("csetup_sent_msg"), gate.index('subRole == "admin"'))
        self.assertLess(gate.index("R.string.common_ok"), gate.index('subRole == "admin"'))
        self.assertRegex(gate, r"\.show\(\)")

    def test_15c_admin_path_and_strings_are_untouched(self):
        self.assertIn('name="csetup_sent_go"', kt_strings())
        self.assertIn('name="csetup_sent_msg"', kt_strings())
        setup = strip_comments(kt("ClassSetupActivity.kt"))
        # الگوی موجودِ پنهان‌کردن دکمهٔ حذف برای منشی دست‌نخورده می‌ماند
        self.assertRegex(setup, r'if\s*\(subRole\s*==\s*"secretary"\)\s*\{\s*holder\.btnRemove\.visibility\s*=\s*View\.GONE')
        # مقصد دکمهٔ ادمین همان صفحهٔ صف تأیید است
        self.assertIn("PendingClassesActivity::class.java", setup)


class TestItem14TeacherInsideClassAdminActions(unittest.TestCase):
    """آیتم ۱۴ — داخل کلاس در پنل معلم: قسمت‌های ادمین مخفی (فقط ادمین باز باشد).

    مسیر (طبق گفتهٔ کارفرما): پنل معلم → بنر کلاس → «۱) ثبت حضور و غیاب»
    (`AttendanceActivity`) → نام دانش‌آموز در لیست حضور و غیاب (`AttendanceActivity:934`)
    → `StudentProfileActivity`. همین صفحه از «راه‌اندازی کلاس» (`ClassSetupActivity:505`)
    و «کلاس زنده» (`LiveRosterActivity:160` و `LiveClassActivity:287`) هم باز می‌شود.

    قبل از فیکس، تنها چک نقشِ `StudentProfileActivity` این بود:
    `if (subRole == "secretary")` → فقط «حذف کامل دانش‌آموز» GONE. یعنی **معلم** همهٔ
    این‌ها را فعال می‌دید: «صدور فیش و ثبت حواله» (→ InvoiceActivity)، کلید «تعلیق
    دانش‌آموز» (→ POST admin/students/{id}/toggle_suspend)، «حذف کامل دانش‌آموز»
    (→ DELETE admin/students/{id})، «افزودن قسط جدید»، «پرداخت/یادآوری» روی هر قسط،
    «ارسال لینک پورتال به اولیا» و ویرایش پروفایل (تغییر عکس هم روی imgProfile).

    تصمیم دامنه: گارد روی `subRole == "teacher"` است نه `!= "admin"`، چون «منشی» در این
    اپ نقش وصول پول است (endpointهای مالی سرور `("admin","secretary")` را می‌پذیرند) و
    رفتار قبلی‌اش (فقط حذفِ «حذف کامل دانش‌آموز») عمداً دست‌نخورده می‌ماند.
    """

    ADMIN_VIEWS = ("btnInvoice", "btnAddInstallment", "cardSuspendStudent",
                   "btnDeleteStudent", "btnSendPortalLink", "fabEditProfile")

    def test_14a_teacher_gate_hides_every_admin_part(self):
        body = function_body(kt("StudentProfileActivity.kt"), "initViews")
        self.assertRegex(body, r'getSharedPreferences\("UserCreds"')
        self.assertRegex(body, r'getString\("USER_SUB_ROLE",\s*"admin"\)')
        self.assertRegex(body, r'isTeacherUser\s*=\s*subRole\s*==\s*"teacher"')
        gate = body[body.index("isTeacherUser"):]
        for view in self.ADMIN_VIEWS:
            self.assertRegex(gate, rf"{view}[^{{}}]{{0,60}}?visibility\s*=\s*View\.GONE",
                             f"{view} باید برای معلم پنهان شود")
        # بخش تعلیق باید کامل پنهان شود (نه فقط کلید، که عنوان/توضیح هم بماند)
        self.assertIn("@+id/cardSuspendStudent", layout("activity_student_profile.xml"))

    def test_14b_admin_listeners_are_not_registered_for_teachers(self):
        """پنهان + بدون listener ⇒ هیچ راه فراری برای معلم نمی‌ماند."""
        src = kt("StudentProfileActivity.kt")
        body = function_body(src, "initViews")
        self.assertIn("if (!isTeacherUser)", body, "باید شاخهٔ «غیر معلم» برای listenerها باشد")
        guarded = body[body.index("if (!isTeacherUser)"):]
        for listener in ("btnAddInstallment.setOnClickListener",
                         "R.id.btnDeleteStudent).setOnClickListener",
                         "R.id.btnSendPortalLink).setOnClickListener",
                         "imgProfile).setOnClickListener",
                         "switchSuspend.setOnClickListener",
                         "btnInvoice.setOnClickListener"):
            self.assertIn(listener, guarded, f"{listener} باید داخل شاخهٔ غیرمعلم باشد")
        # دکمهٔ ویرایش پروفایل در onCreate سیم‌کشی می‌شود (initViews پیش از آن صدا زده می‌شود)
        create = function_body(src, "onCreate")
        self.assertIn("if (!isTeacherUser)", create)
        self.assertLess(create.index("if (!isTeacherUser)"), create.index("R.id.fabEditProfile"))

    def test_14c_secretary_keeps_money_actions_and_old_behavior(self):
        """منشی مثل قبل فقط «حذف کامل دانش‌آموز» را نمی‌بیند؛ حواله/تعلیق/قسط برایش می‌ماند."""
        body = function_body(kt("StudentProfileActivity.kt"), "initViews")
        self.assertRegex(body, r'if\s*\(subRole\s*==\s*"secretary"\)')
        self.assertRegex(body, r'R\.id\.btnDeleteStudent\)\.visibility\s*=\s*View\.GONE')
        self.assertNotRegex(body, re.compile(r'isTeacherUser\s*=\s*subRole\s*!=\s*"admin"'),
                            "گارد باید روی «teacher» باشد تا منشی دسترسی وصول پول را از دست ندهد")

    def test_14d_installment_pay_and_remind_hidden_for_teachers(self):
        src = kt("StudentProfileActivity.kt")
        body = function_body(src, "onBindViewHolder")  # تنها آداپتر این فایل: InstallmentAdapter
        self.assertIn("isTeacherUser", body, "اکشن‌های هر قسط باید برای معلم پنهان شود")
        self.assertRegex(body, r"holder\.layoutActions\.visibility\s*=\s*View\.GONE")
        self.assertIn("holder.btnPay.setOnClickListener", body)
        self.assertIn("holder.btnRemind.setOnClickListener", body)

    def test_14e_readonly_profile_and_navigation_stay_intact(self):
        src = kt("StudentProfileActivity.kt")
        body = function_body(src, "initViews")
        gate = body[body.index("isTeacherUser"):]
        for keep in ("tabLayout", "cardContent", "tvContent", "rvInstallments", "cardInstallments"):
            self.assertNotRegex(gate, re.compile(re.escape(keep) + r"[^\n]{0,40}View\.GONE"),
                                f"{keep} بخشی از نمای خواندنی معلم است و نباید پنهان شود")
        # مسیر ورود از دل کلاس/حضور و غیاب سر جایش می‌ماند (فقط اکشن‌ها پنهان شده‌اند)
        self.assertIn("StudentProfileActivity::class.java", strip_comments(kt("AttendanceActivity.kt")))
        self.assertIn("StudentProfileActivity::class.java", strip_comments(kt("ClassSetupActivity.kt")))


if __name__ == "__main__":
    unittest.main()
