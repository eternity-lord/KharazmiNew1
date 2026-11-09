# گروه ۴ — نمایش خراب، آیتم ۱۷ (پنل ادمین)
#
# بازتولید آیتم ۱۷:
# endpoint واقعی /classes/{id}/students_full روی کپی DB پاسخ غیرخالی می‌دهد؛
# بنابراین خالی‌بودن لیست در پنل ادمین از داده/endpoint نیست. در ClassDetailActivity
# RecyclerView در onCreate عمداً GONE می‌شود، اما شاخهٔ تب «لیست دانش‌آموزان» آن را
# دوباره VISIBLE نمی‌کند. این تست قرارداد binding/visibility را قفل می‌کند.
#
# طبق قانون پروژه این تست ایستا است: در این sandbox کامپایل اندروید انجام نمی‌شود.
import os
import re
import unittest


SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(SERVER_DIR)
KT_DIR = os.path.join(
    REPO_ROOT,
    "KharazmiAdmin",
    "app",
    "src",
    "main",
    "java",
    "com",
    "example",
    "kharazmiadmin",
)


def kt(name: str) -> str:
    path = os.path.join(KT_DIR, name)
    assert os.path.exists(path), f"فایل کاتلین پیدا نشد: {path}"
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def function_body(source: str, name: str) -> str:
    """بدنهٔ تابع تا تابع هم‌سطح بعدی؛ همان الگوی گاردهای ایستای پروژه."""
    match = re.search(
        r"\n\s*(?:(?:private|internal|public|override|open|suspend)\s+)*fun\s+"
        + re.escape(name)
        + r"\s*\(",
        source,
    )
    assert match, f"تابع {name} در سورس پیدا نشد"
    rest = source[match.end() :]
    nxt = re.search(r"\n\s{0,4}(?:private |internal |public |override )*fun\s+\w+", rest)
    return rest[: nxt.start()] if nxt else rest


class TestItem17AdminClassStudentList(unittest.TestCase):
    """آیتم ۱۷ — لیست دانش‌آموزان کلاس در پنل ادمین نباید با دادهٔ موجود ناپدید شود."""

    def test_17a_student_tab_makes_the_bound_recycler_view_visible(self):
        src = kt("ClassDetailActivity.kt")
        body = function_body(src, "updateUI")
        student_tab_start = body.index("1 ->")
        student_tab = body[student_tab_start:]
        self.assertIn("rvStudents", src)
        self.assertRegex(
            student_tab,
            r"rvStudents\.visibility\s*=\s*View\.VISIBLE",
            "شاخهٔ تب لیست دانش‌آموزان باید RecyclerView متصل به adapter را نمایش دهد",
        )

    def test_17b_the_adapter_is_bound_to_the_same_recycler_view(self):
        body = function_body(kt("ClassDetailActivity.kt"), "onCreate")
        self.assertIn("rvStudents = findViewById(R.id.rvStudents)", body)
        self.assertIn("rvStudents.adapter = studentAdapter", body)
        self.assertIn("rvStudents.visibility = View.GONE", body)

    def test_17c_the_admin_class_detail_uses_the_real_students_endpoint(self):
        src = kt("ClassDetailActivity.kt")
        self.assertIn('@GET("classes/{id}/students_full")', src)
        self.assertIn("api.getClassStudentsFull(classId)", src)


def py(name: str) -> str:
    path = os.path.join(SERVER_DIR, name)
    assert os.path.exists(path), f"فایل Python پیدا نشد: {path}"
    with open(path, encoding="utf-8") as handle:
        return handle.read()


class TestItems18To21TeacherAndAdminBanners(unittest.TestCase):
    """قرارداد آیتم‌های باقی‌ماندهٔ گروه ۴؛ پنل هر مورد جداگانه قفل می‌شود."""

    def test_18_teacher_class_student_list_reaches_the_shared_fixed_screen(self):
        """مسیر پنل معلم باید برای کلاس تأییدشده به همان صفحهٔ جزئیات برود.

        visibilityِ RecyclerView در آیتم ۱۷ روی همین Activity فیکس شده و این تست
        مسیر معلم را جداگانه تأیید می‌کند؛ مسیر endpoint معلم به endpoint جزئیات
        دانش‌آموزان نیز در همان صفحهٔ مشترک اجرا می‌شود.
        """
        fetch_body = function_body(kt("TeacherDashboardActivity.kt"), "fetchClasses")
        self.assertIn("ClassDetailActivity::class.java", fetch_body)
        self.assertIn('putExtra("CLASS_ID", selectedClass.id)', fetch_body)

        detail_src = kt("ClassDetailActivity.kt")
        student_tab = function_body(detail_src, "updateUI")
        student_tab = student_tab[student_tab.index("1 ->"):]
        self.assertRegex(student_tab, r"rvStudents\.visibility\s*=\s*View\.VISIBLE")
        self.assertIn("api.getClassStudentsFull(classId)", detail_src)

    def test_19_teacher_banner_binds_name_and_theme_explicitly(self):
        """بنر پنل معلم باید title و bg_color پاسخ واقعی را قطعی روی ویجت بنشاند."""
        body = function_body(kt("TeacherDashboardActivity.kt"), "onBindViewHolder")
        self.assertRegex(body, r"val classTitle\s*=\s*item\.title\?\.trim\(\)\.orEmpty\(\)")
        self.assertRegex(body, r"holder\.title\.text\s*=\s*classTitle\.ifEmpty")
        self.assertRegex(body, r"holder\.title\.visibility\s*=\s*(android\.view\.)?View\.VISIBLE")
        self.assertRegex(body, r"val cardColor\s*=\s*item\.bg_color")
        self.assertIn("Color.parseColor(cardColor)", body)

    def test_20_teacher_endpoint_exposes_the_same_debt_breakdown_as_admin_classes(self):
        """منبع بدهی پنل معلم باید همان محاسبهٔ endpoint لیست کلاس‌های ادمین باشد."""
        src = py("routers/teachers.py")
        start = src.index('@router.get("/teachers/{teacher_id}/classes")')
        end = src.index('@router.get("/teachers/{teacher_id}/incomplete_classes")', start)
        route = src[start:end]
        for key in ("total_debt", "debt_to_teacher", "debt_to_institute"):
            self.assertIn(f'"{key}"', route, f"endpoint معلم باید {key} را برگرداند")
        self.assertIn("calculate_enrollment_debt", route)

        body = function_body(kt("TeacherDashboardActivity.kt"), "onBindViewHolder")
        # بنر فقط دو بدهی قابل انتساب به همین کلاس را نشان می‌دهد؛ بدهی کل حذف شده است.
        self.assertNotIn("tvTotalDebt", kt("TeacherDashboardActivity.kt"))
        self.assertNotIn("tvTotalDebt", kt("ClassManagementActivity.kt"))
        for view_id, field in (("tvTeacherDebt", "debt_to_teacher"),
                               ("tvInstituteDebt", "debt_to_institute")):
            self.assertIn(f"R.id.{view_id}", kt("TeacherDashboardActivity.kt"))
            self.assertRegex(body, rf"holder\.{view_id}\.text.*item\.{field}")

    def test_21_admin_class_banner_hides_unregistered_gender_text_only_in_admin_adapter(self):
        """gender_type در مدل می‌ماند؛ فقط چیپِ بنر مدیریت کلاس‌های ادمین مخفی می‌شود."""
        body = function_body(kt("ClassManagementActivity.kt"), "onBindViewHolder")
        self.assertRegex(body, r"holder\.tvGender\.visibility\s*=\s*View\.GONE")
        self.assertIn("holder.tvGender", body)
        teacher_body = function_body(kt("TeacherDashboardActivity.kt"), "onBindViewHolder")
        self.assertNotIn("holder.tvGender.visibility", teacher_body,
                         "فیکس آیتم ۲۱ نباید گارد ادمین را به adapter پنل معلم منتقل کند")


if __name__ == "__main__":
    unittest.main()
