"""شاهدِ کورپسِ نقشهٔ پین در اوراکلِ `KharazmiAdmin/verify_kotlin_refactor.py`.

چرا لازم است
--------------
`--pins` مجوزِ جابه‌جاییِ کدِ Kotlin است: «پینی ندارد» یعنی آزاد است. پس اگر کورپسِ آن
ناقص باشد، اوراکل بی‌صدا مجوزِ شکستنِ تست‌ها را می‌دهد. این دقیقاً همان کلاسی از باگ است
که در این پروژه بارها هزینه داد: **یک خواندنِ ناموفق، صفر/پاک گزارش شود.**

اتفاقی که افتاد: ثابتِ `TEST_DIRS` در اوراکل پوشهٔ تستِ سمتِ سرور را با `H` بزرگ نوشته بود
— پوشه‌ای که وجود ندارد، چون نامِ واقعی با `h` کوچک است. خوشبختانه آن ثابت **مرده** بود
(کورپس از `git ls-files` در `test_files()` می‌آید) و پین‌ها واقعاً دیده می‌شدند؛ ولی یک مینِ
کارگذاشته‌شده بود: هر کس روزی از آن استفاده می‌کرد، ۸۰ فایلِ تستِ سمتِ سرور را از دست
می‌داد — همان فایل‌هایی که پین‌هایِ سختِ Kotlin در آن‌هاست.

این تست‌ها سه کار می‌کنند: ثابت‌ها را با فایل‌سیستم می‌سنجند (کنترلِ مثبت)، غیرتهیِ نقشهٔ
پین از سمتِ سرور را اثبات می‌کنند، و کلِ کلاسِ این غلطِ املایی را در همهٔ فایل‌هایِ کدِ
tracked ممنوع می‌کنند.
"""

from __future__ import annotations

import subprocess

from KharazmiAdmin.verify_kotlin_refactor import (
    MIN_FILES_PER_TEST_DIR,
    MIN_TEST_FILES,
    REQUIRED_TESTS,
    ROOT,
    TEST_DIRS,
    collect_pins,
)
from KharazmiAdmin.verify_kotlin_refactor import test_files as oracle_test_files

# تابعِ `test_files` اوراکل عمداً با alias وارد می‌شود: pytest هر نامِ `test_*` در فضایِ
# نامِ ماژول را به‌عنوانِ تست جمع می‌کند، پس importِ بی‌alias یک «تستِ» کاذب می‌ساخت که
# تنها اثرش بادکردنِ شمارِ سوئیت بود (۵ تست ولی ۶ passed).
# شمارِ واقعیِ امروز: ۱۱۸ فایلِ تست (۸۰ در Kharazmi_Server/tests و ۳۸ در tests/)
SERVER_TESTS = ROOT / "Kharazmi_Server" / "tests"
CODE_GLOBS = ("*.py", "*.kt", "*.kts", "*.yml", "*.yaml", "*.toml", "*.ini", "*.cfg",
              "*.json", "*.gradle", "*.bat", "*.xml")
# خودِ این توکن‌ها در این فایل **نمی‌آیند** وگرنه گاردِ پایین رویِ تستِ خودش می‌شکست؛
# از قطعه‌هایِ جدا ساخته می‌شوند تا درسِ «assert نباید توضیحِ خودش را match کند» رعایت شود.
BAD_TOKENS = ("K" + "Harazmi_Server", "K" + "HarazmiAdmin")


def test_every_test_dir_constant_exists_on_disk_and_holds_python_tests():
    """کنترلِ مثبت رویِ **خودِ ثابت‌ها** — همان تستی که غلطِ املایِ H بزرگ را می‌گرفت."""
    assert TEST_DIRS, "TEST_DIRS خالی است"
    for d in TEST_DIRS:
        rel = str(d.relative_to(ROOT))
        assert d.exists(), f"پوشهٔ تست {rel} وجود ندارد — املایش را با git ls-files بسنجید"
        pys = [p for p in d.rglob("*.py") if "__pycache__" not in p.parts]
        assert len(pys) >= MIN_FILES_PER_TEST_DIR[rel], (rel, len(pys))
    assert SERVER_TESTS.exists()
    assert MIN_FILES_PER_TEST_DIR["Kharazmi_Server/tests"] >= 60


def test_corpus_covers_both_directories_and_the_required_pin_file():
    corpus = oracle_test_files()
    assert len(corpus) >= MIN_TEST_FILES, len(corpus)
    names = {p.name for p in corpus}
    assert names >= REQUIRED_TESTS, sorted(REQUIRED_TESTS - names)
    for d in TEST_DIRS:
        rel = str(d.relative_to(ROOT))
        n = sum(1 for p in corpus if d in p.parents)
        assert n >= MIN_FILES_PER_TEST_DIR[rel], (rel, n)
    # test_files() خودش اگر فایلِ tracked روی دیسک نباشد ABORT می‌کند؛ این هم تأییدِ مستقل
    assert all(p.exists() for p in corpus)


def test_the_pin_corpus_actually_sees_the_server_side_pins():
    """غیرتهی نبودنِ نقشهٔ پین: پین‌هایِ سختِ Kotlin در تست‌هایِ سمتِ سرورند.

    اگر روزی کورپس به `tests/` محدود شود (یا پوشهٔ سرور تغییرِ نام دهد و کفِ سراسری پاس
    بماند)، این تست قرمز می‌شود — نه اینکه اوراکل بی‌صدا بگوید «پینی نیست».
    """
    contributors = {}
    for p in oracle_test_files():
        if SERVER_TESTS not in p.parents:
            continue
        try:
            kts, lits = collect_pins(p)
        except SyntaxError:
            continue
        if kts:
            contributors[p.name] = (len(kts), len(lits))
    assert contributors, "هیچ تستِ سمتِ سروری فایلِ .kt را صدا نمی‌زند — نقشهٔ پین ناقص است"
    # امروز ۹ فایل (از ۱۴ فایلِ کورپس؛ ۵ تایِ دیگر در tests/route_audit‌اند). کف رویِ ۸
    # است تا جابه‌جاییِ یک فایل شکستِ کاذب ندهد ولی افتِ واقعی (مثلاً محدودشدنِ کورپس به
    # یک پوشه) حتماً گرفته شود.
    assert len(contributors) >= 8, sorted(contributors)
    key = "test_android_resources_static.py"
    assert key in contributors, sorted(contributors)
    kt_refs, literals = contributors[key]
    assert kt_refs >= 10, kt_refs          # امروز ۱۷
    assert literals >= 100, literals       # امروز ۲۱۷


def test_no_tracked_code_file_misspells_either_root_directory():
    """گاردِ سراسری برایِ کلِ کلاسِ این غلط: H بزرگ در نامِ دو پوشهٔ ریشه.

    checkpointها و docs عمداً مستثنا هستند چون خودِ غلط را نقل می‌کنند تا درسش بماند؛
    ممنوعیت فقط برایِ فایل‌هایِ **کد** است که آن مسیرها را واقعاً مصرف می‌کنند.
    """
    listed = subprocess.run(["git", "ls-files", "--", *CODE_GLOBS], cwd=ROOT,
                            capture_output=True, text=True, check=True).stdout.split()
    assert len(listed) > 500, len(listed)      # کنترلِ مثبت: واقعاً کورپس دیده‌ایم (امروز ۵۶۴)
    bad = []
    for f in listed:
        p = ROOT / f
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        bad += [(f, tok) for tok in BAD_TOKENS if tok in text]
    assert not bad, bad


def test_the_real_server_root_is_the_lowercase_one_per_the_git_index():
    """املا را از رویِ خودِ indexِ git اثبات می‌کند، نه از رویِ حدس یا readdirِ لحظه‌ای."""
    out = subprocess.run(["git", "ls-files", "--", "*gaj_db.db"], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout.split()
    assert out, "دیتابیسِ واقعی tracked نیست؟"
    good = "K" + "harazmi_Server/"
    bad = "K" + "Harazmi_Server/"
    assert any(f.startswith(good) for f in out), out
    assert not any(f.startswith(bad) for f in out), out
