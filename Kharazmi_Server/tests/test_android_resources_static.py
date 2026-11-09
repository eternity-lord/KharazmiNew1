# test_android_resources_static.py
# گاردهای ایستا برای منابع اپ اندروید (KharazmiAdmin) — چون در این محیط Gradle/JDK نیست و
# `assembleDebug` اجرا نمی‌شود، این تست‌ها همان خطاهایی را می‌گیرند که «Resource and asset merger»
# یا aapt2 هنگام build می‌گیرد:
#   ۱) نام تکراری در یک فایل `values*/strings.xml`  ⇒ خطای واقعی build:
#      «Found item String/<name> more than one time»
#   ۲) هر `R.string.X` استفاده‌شده در Kotlin باید در `values/strings.xml` تعریف شده باشد.
#   ۳) تعداد/نوع آرگومان‌های `getString(R.string.X, …)` باید با placeholderهای رشته بخواند
#      (وگرنه در زمان اجرا MissingFormatArgumentException).
#   ۴) هر `R.<نوع>.<نام>` استفاده‌شده در Kotlin باید منبع متناظر داشته باشد (لینک R).
#   ۵) گارد چیپ: هیچ `Chip` ای نباید چندخطی باشد. `aapt2` این را نمی‌گیرد (خطای build نیست) ولی
#      در زمان اجرا inflate را با UnsupportedOperationException می‌ترکاند ⇒ کرش صفحه.
#
# انگیزهٔ واقعی: باگ build «attendance_server_error دو بار تعریف شده بود» (یک بار با ۲ آرگومان و
# یک بار با ۱ آرگومان) که mergeDebugResources را می‌شکست؛ و باگ کرش «Chip does not support
# multi-line text» در layout/item_class_row.xml (صفحهٔ مدیریت کلاس‌ها).
import os
import re
import unittest
import xml.etree.ElementTree as ET

SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(SERVER_DIR)
ANDROID_MAIN = os.path.join(REPO_ROOT, "KharazmiAdmin", "app", "src", "main")
RES_DIR = os.path.join(ANDROID_MAIN, "res")
JAVA_DIR = os.path.join(ANDROID_MAIN, "java")

# نوع‌های منابعی که aapt2 برای هر پوشهٔ res تولید می‌کند (برای چک لینک R)
RES_FOLDERS = {
    "layout": "layout", "drawable": "drawable", "mipmap": "mipmap-anydpi-v26", "font": "font",
    "anim": "anim", "color": "color", "menu": "menu", "xml": "xml", "raw": "raw",
}


def _strip_comments(source: str) -> str:
    """کامنت‌های کاتلینی/بلوکی را حذف می‌کند تا اسکن روی کد واقعی باشد، نه توضیحات."""
    source = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), source, flags=re.S)
    return re.sub(r"^\s*//.*$", "", source, flags=re.M)


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def _strings_files():
    return sorted(
        os.path.join(RES_DIR, folder, "strings.xml")
        for folder in os.listdir(RES_DIR)
        if folder.startswith("values") and os.path.exists(os.path.join(RES_DIR, folder, "strings.xml"))
    )


def _string_entries(path):
    """[(نام, متن)] از یک فایل strings.xml — با xml.etree."""
    root = ET.parse(path).getroot()
    return [(el.get("name"), "".join(el.itertext())) for el in root if el.tag == "string" and el.get("name")]


def _placeholders(text: str):
    """تعداد/ترتیب placeholderهای یک رشتهٔ فرمت‌دار اندروید.

    • positional مثل `%1$d` / `%2$s` / `%1$.2f` ⇒ نوع‌ها به ترتیب شماره
    • غیر-positional مثل `%,d` (جداکنندهٔ هزارگان، همان الگوی `common_toman_format`) ⇒ یک آرگومان
    • `%%` (درصد خام) شمرده نمی‌شود.
    """
    positional = {int(m.group(1)): m.group(2).rstrip(".") for m in re.finditer(r"%(\d+)\$([a-zA-Z.]+)", text)}
    if positional:
        return [kind for _index, kind in sorted(positional.items())]
    without_escapes = text.replace("%%", "")
    return ["arg"] * len(re.findall(r"%[-#+ 0,(]*\d*(?:\.\d+)?[a-zA-Z]", without_escapes))


def _string_format_arg_spans(source: str):
    """بازه‌های متنی که آرگومان‌های `String.format(...)` هستند.

    چرا لازم است: الگوی رایج و درست `String.format(Locale.US, getString(R.string.X), value)` هم
    وجود دارد؛ آنجا `getString` عمداً بدون آرگومان صدا زده می‌شود و `String.format` placeholder
    را پر می‌کند ⇒ نباید ناسازگاری شمرده شود.
    """
    spans = []
    for match in re.finditer(r"String\.format\s*\(", source):
        index = match.end()
        depth = 1
        while index < len(source) and depth > 0:
            char = source[index]
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            index += 1
        spans.append((match.end(), index))
    return spans


def _kotlin_files():
    for root_dir, _dirs, files in os.walk(JAVA_DIR):
        for name in sorted(files):
            if name.endswith((".kt", ".java")):
                yield os.path.join(root_dir, name)


class TestAndroidStringResources(unittest.TestCase):
    """گاردهای ۱ و ۲ — خطاهای قطعی build."""

    def test_1_no_duplicate_string_names_in_any_values_file(self):
        """همان خطای واقعی build: «Found item String/<name> more than one time»."""
        offenders = {}
        files = _strings_files()
        self.assertTrue(files, f"هیچ values*/strings.xml پیدا نشد زیر {RES_DIR}")
        for path in files:
            seen = {}
            for name, _text in _string_entries(path):
                seen[name] = seen.get(name, 0) + 1
            dups = sorted(name for name, count in seen.items() if count > 1)
            if dups:
                offenders[os.path.relpath(path, REPO_ROOT)] = dups
        self.assertEqual(offenders, {}, f"نام رشتهٔ تکراری (build می‌شکند): {offenders}")

    def test_1b_no_duplicate_resource_names_in_any_res_file(self):
        """همین خطا برای رنگ/دایمن/استایل/آی‌دی هم build را می‌شکند — کل پوشهٔ res اسکن می‌شود."""
        offenders = {}
        for root_dir, _dirs, names in os.walk(RES_DIR):
            for name in sorted(names):
                if not name.endswith(".xml"):
                    continue
                path = os.path.join(root_dir, name)
                try:
                    root = ET.parse(path).getroot()
                except ET.ParseError as error:  # XML خراب ⇒ خودش خطای build است
                    offenders[os.path.relpath(path, REPO_ROOT)] = [f"XML نامعتبر: {error}"]
                    continue
                per_tag = {}
                for el in root:
                    key = el.get("name")
                    if not key:
                        continue
                    per_tag.setdefault(el.tag, {})[key] = per_tag.get(el.tag, {}).get(key, 0) + 1
                for tag, counts in per_tag.items():
                    dups = sorted(k for k, v in counts.items() if v > 1)
                    if dups:
                        offenders.setdefault(os.path.relpath(path, REPO_ROOT), []).append(f"{tag}: {dups}")
        self.assertEqual(offenders, {}, f"نام منبع تکراری در یک فایل (build می‌شکند): {offenders}")

    def test_2_every_used_string_key_is_defined(self):
        """هر R.string.X در Kotlin باید در values/strings.xml تعریف شده باشد."""
        defined = {name for name, _text in _string_entries(os.path.join(RES_DIR, "values", "strings.xml"))}
        offenders = {}
        for path in _kotlin_files():
            source = _strip_comments(_read(path))
            for match in re.finditer(r"(?<![\w.])R\.string\.([A-Za-z_][A-Za-z0-9_]*)", source):
                if match.group(1) not in defined:
                    offenders.setdefault(os.path.relpath(path, REPO_ROOT), set()).add(match.group(1))
        self.assertEqual(offenders, {}, f"کلید رشتهٔ تعریف‌نشده: {offenders}")

    def test_3_getstring_arguments_match_placeholders(self):
        """تعداد آرگومان‌های getString باید با placeholderهای همان رشته بخواند."""
        defs = {}
        for path in _strings_files():
            for name, text in _string_entries(path):
                defs.setdefault(name, []).append(text)
        call_re = re.compile(r"getString\(\s*R\.string\.([A-Za-z_][A-Za-z0-9_]*)\s*(,)?")
        offenders = []
        for path in _kotlin_files():
            source = _strip_comments(_read(path))
            format_spans = _string_format_arg_spans(source)
            for match in call_re.finditer(source):
                name = match.group(1)
                if name not in defs:
                    continue  # گارد تعریف‌نشده‌ها در تست ۲
                if not match.group(2):
                    n_args = 0
                else:
                    # شمارش آرگومان‌ها تا پرانتز بستهٔ متناظر (با احتساب پرانتزهای تودرتو)
                    index, depth, buffer, args = match.end(), 1, "", []
                    while index < len(source) and depth > 0:
                        char = source[index]
                        if char == "(":
                            depth += 1
                            buffer += char
                        elif char == ")":
                            depth -= 1
                            if depth == 0:
                                break
                            buffer += char
                        elif char == "," and depth == 1:
                            args.append(buffer)
                            buffer = ""
                        else:
                            buffer += char
                        index += 1
                    if buffer.strip():
                        args.append(buffer)
                    n_args = len([a for a in args if a.strip()])
                expected = {len(_placeholders(text)) for text in defs[name]}
                # getString بدون آرگومان داخل String.format(...) درست است (پُر شدن بیرونی placeholder)
                wrapped_in_format = n_args == 0 and any(start <= match.start() < end for start, end in format_spans)
                if n_args not in expected and not wrapped_in_format:
                    line = source[: match.start()].count("\n") + 1
                    offenders.append(
                        f"{os.path.relpath(path, REPO_ROOT)}:{line} → R.string.{name} "
                        f"args={n_args} ولی placeholder={sorted(expected)}"
                    )
        self.assertEqual(offenders, [], "ناسازگاری آرگومان/placeholder:\n" + "\n".join(offenders))

    def test_4_r_references_resolve_to_real_resources(self):
        """لینک R: هر R.<نوع>.<نام> در Kotlin باید منبع متناظر در res داشته باشد."""
        defined = {}
        for folder in os.listdir(RES_DIR):
            if not folder.startswith("values"):
                continue
            for name in os.listdir(os.path.join(RES_DIR, folder)):
                if not name.endswith(".xml"):
                    continue
                try:
                    root = ET.parse(os.path.join(RES_DIR, folder, name)).getroot()
                except ET.ParseError:  # pragma: no cover - فایل XML خراب، در جای دیگری دیده می‌شود
                    continue
                for el in root:
                    key = el.get("name")
                    if not key:
                        continue
                    if el.tag in ("string", "plurals", "string-array"):
                        defined.setdefault("string", set()).add(key)
                    elif el.tag == "color":
                        defined.setdefault("color", set()).add(key)
                    elif el.tag == "dimen":
                        defined.setdefault("dimen", set()).add(key)
                    elif el.tag == "style":
                        defined.setdefault("style", set()).add(key.replace(".", "_"))
                    elif el.tag == "item" and el.get("type"):
                        defined.setdefault(el.get("type"), set()).add(key)
        for kind, folder in RES_FOLDERS.items():
            if not os.path.isdir(os.path.join(RES_DIR, folder)):
                continue
            for name in os.listdir(os.path.join(RES_DIR, folder)):
                defined.setdefault(kind, set()).add(os.path.splitext(name)[0])
        # شناسه‌ها (R.id.*) از layout/menu/xml ساخته می‌شوند — aapt2 همان‌ها را تولید می‌کند.
        id_sources = []
        for folder in os.listdir(RES_DIR):
            if folder.startswith(("layout", "menu", "xml", "anim")) or folder.startswith("values"):
                folder_path = os.path.join(RES_DIR, folder)
                if os.path.isdir(folder_path):
                    id_sources.extend(os.path.join(folder_path, n) for n in os.listdir(folder_path) if n.endswith(".xml"))
        for path in id_sources:
            try:
                source = _read(path)
            except OSError:  # pragma: no cover
                continue
            defined.setdefault("id", set()).update(re.findall(r"@\+?id/([A-Za-z_][A-Za-z0-9_]*)", source))

        offenders = []
        for path in _kotlin_files():
            source = _strip_comments(_read(path))
            for match in re.finditer(r"(?<![\w.])R\.([a-z]+)\.([A-Za-z_][A-Za-z0-9_]*)", source):
                kind, name = match.group(1), match.group(2)
                if kind not in defined:
                    continue
                if name not in defined[kind]:
                    line = source[: match.start()].count("\n") + 1
                    offenders.append(f"{os.path.relpath(path, REPO_ROOT)}:{line} → R.{kind}.{name}")
        self.assertEqual(offenders, [], "ارجاع R بدون منبع:\n" + "\n".join(offenders))


class TestAttendanceServerErrorRegression(unittest.TestCase):
    """گارد رگرسیون همان باگ build: کلید تکراری در AttendanceActivity."""

    def test_two_distinct_error_keys_with_correct_arity(self):
        """پیام «خطای سرور با جزئیات» (۲ آرگومان) و «۵۰۰ با پیام تلاش مجدد» (۱ آرگومان) هر دو
        باید باشند ولی با **کلیدهای متفاوت** — قبلاً هر دو `attendance_server_error` بودند و
        mergeDebugResources را می‌شکستند."""
        defs = dict(_string_entries(os.path.join(RES_DIR, "values", "strings.xml")))
        self.assertIn("attendance_server_error", defs)
        self.assertNotIn(None, defs)
        self.assertTrue("attendance_server_error_retry" in defs,
                        "کلید `attendance_server_error_retry` تعریف نشده (باگ build: کلید تکراری)")
        self.assertEqual(_placeholders(defs["attendance_server_error"]), ["d", "s"],
                         "پیام اصلی باید (%1$d): %2$s باشد")
        self.assertEqual(_placeholders(defs["attendance_server_error_retry"]), ["d"],
                         "پیام ریتِرای باید تک‌آرگومانی باشد")

        source = _strip_comments(_read(os.path.join(JAVA_DIR, "com", "example", "kharazmiadmin",
                                                    "AttendanceActivity.kt")))
        # فراخوانی دوعملوندی (سمت بارگذاری کلیدهای حضور) روی پیام اصلی مانده است
        self.assertRegex(source, r"R\.string\.attendance_server_error,\s*e\.code\(\),\s*detail",
                         "فراخوانی ۲-آرگومانی باید از کلید اصلی استفاده کند")
        # فراخوانی تک‌آرگومانی (۵۰۰..۵۹۹ در ثبت جلسه) باید به کلید retry منتقل شده باشد
        self.assertRegex(source, r"R\.string\.attendance_server_error_retry,\s*e\.code\(\)",
                         "فراخوانی ۱-آرگومانی باید از کلید retry استفاده کند")


# ---------------------------------------------------------------------------
# FIX(chip-multiline) — گارد ۵: هیچ Chip ای نباید چندخطی باشد
#
# خطای واقعی روی دستگاه کاربر:
#   java.lang.UnsupportedOperationException: Chip does not support multi-line text
#     at com.google.android.material.chip.Chip.setMaxLines(Chip.java:699)
#     at android.widget.TextView.<init>(TextView.java:1390)
#     ⇒ InflateException: Binary XML file line #123 in ...:layout/item_class_row
#     ⇒ کرش ClassManagementActivity (صفحهٔ «مدیریت کلاس‌ها»)
#
# چرا: کلاس Chip چهار متد متنی TextView را قفل کرده و اگر مقدار چندخطی بگیرند استثنا می‌دهد:
#   setSingleLine(false) · setLines(>1) · setMinLines(>1) · setMaxLines(>1)
# این مقادیر از **زنجیرهٔ style** هم به Chip می‌رسند (مثل `style="@style/GajChipStyle"`)،
# از **theme** هم (چون theme آخرین fallback حلِ attribute است). aapt2 هیچ‌کدام را خطای build
# نمی‌داند ⇒ فقط با این گارد ایستا یا با کرش روی دستگاه لو می‌رود.
# ---------------------------------------------------------------------------

CHIP_VIEW_TAG = "com.google.android.material.chip.Chip"
# attributeهایی که Chip روی آن‌ها سخت‌گیر است (هر کدام > ۱ خط / غیر تک‌خطی ⇒ استثنا)
CHIP_TEXT_CONSTRAINT_ATTRS = ("android:singleLine", "android:maxLines", "android:minLines", "android:lines")

_START_TAG_RE = re.compile(
    r"<([A-Za-z_][\w.:]*)((?:\s+[\w.:-]+\s*=\s*(?:\"[^\"]*\"|'[^']*'))*)\s*/?>",
    re.S,
)
_ATTR_RE = re.compile(r"([\w.:-]+)\s*=\s*(?:\"([^\"]*)\"|'([^']*)')", re.S)
_STYLE_TAG_RE = re.compile(r"<style\b(?P<attrs>[^>]*)>", re.S)
_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)


def _strip_xml_comments(source: str) -> str:
    """کامنت‌های XML را (با حفظ شمارهٔ خط‌ها) حذف می‌کند تا اسکن روی محتوای واقعی باشد."""
    return _COMMENT_RE.sub(lambda m: "\n" * m.group(0).count("\n"), source)


def _line_of(source: str, index: int) -> int:
    return source[:index].count("\n") + 1


def _attrs_of(attr_block: str) -> dict:
    return {m.group(1): (m.group(2) if m.group(2) is not None else m.group(3)) for m in _ATTR_RE.finditer(attr_block)}


def _view_tags(source: str):
    """[(نام تگ, دیکشنری attributeها, شمارهٔ خط)] برای همهٔ تگ‌های بازِ یک layout."""
    stripped = _strip_xml_comments(source)
    for match in _START_TAG_RE.finditer(stripped):
        yield match.group(1), _attrs_of(match.group(2)), _line_of(source, match.start())


def _layout_files():
    folders = sorted(
        os.path.join(RES_DIR, name)
        for name in os.listdir(RES_DIR)
        if name == "layout" or name.startswith("layout-")
    )
    files = []
    for folder in folders:
        files += [os.path.join(folder, name) for name in sorted(os.listdir(folder)) if name.endswith(".xml")]
    return files


def _values_dirs():
    return sorted(
        os.path.join(RES_DIR, name)
        for name in os.listdir(RES_DIR)
        if name == "values" or name.startswith("values-")
    )


def _style_definitions():
    """{پیکربندی: {نام استایل: {parent, items, file, line}}} — مثل values و values-night جدا نگه داشته می‌شوند."""
    definitions = {}
    for folder in _values_dirs():
        config = os.path.basename(folder)
        bucket = definitions.setdefault(config, {})
        for name in sorted(os.listdir(folder)):
            if not name.endswith(".xml"):
                continue
            path = os.path.join(folder, name)
            source = _read(path)
            if "<style" not in source:
                continue
            lines_by_name = {}
            for match in _STYLE_TAG_RE.finditer(source):
                style_name = _attrs_of(match.group("attrs")).get("name")
                if style_name and style_name not in lines_by_name:
                    lines_by_name[style_name] = _line_of(source, match.start())
            for element in ET.parse(path).getroot():
                if element.tag != "style" or not element.get("name"):
                    continue
                style_name = element.get("name")
                if style_name in bucket:  # نام تکراری ⇒ همان گارد ۱ آن را می‌گیرد
                    continue
                bucket[style_name] = {
                    "parent": element.get("parent") or "",
                    "items": {
                        item.get("name"): "".join(item.itertext()).strip()
                        for item in element
                        if item.get("name")
                    },
                    "file": path,
                    "line": lines_by_name.get(style_name, 0),
                }
    return definitions


def _style_chain(style_name: str, config: str, definitions: dict):
    """[(نام استایل, تعریف)] از خودِ استایل تا والدها — با fallback از values-night به values."""
    chain = []
    seen = set()
    current = style_name
    while current and current not in seen:
        seen.add(current)
        definition = definitions.get(config, {}).get(current) or definitions.get("values", {}).get(current)
        if definition is None:
            break
        chain.append((current, definition))
        parent = definition["parent"]
        if not parent or parent.startswith(("@android:", "?")):
            break
        current = parent.split("/")[-1]
    return chain


def _chip_attribute_hazard(attr: str, value: str):
    """آیا این attribute مقدارِ ممنوع برای Chip دارد؟ ⇒ True/False"""
    value = value.strip()
    if attr == "android:singleLine":
        return value.lower() == "false"
    if attr in ("android:maxLines", "android:minLines", "android:lines"):
        if value.startswith(("@", "?")):  # مقدار ارجاعی ⇒ قابل اتکا نیست، محافظه‌کارانه خطا
            return True
        try:
            return int(value) > 1
        except ValueError:
            return True
    return False


def _hazard_origin(attr, element_attrs, style_name, config, definitions):
    """منبع یک attribute برای یک Chip: (مقدار, توضیح منبع) یا (None, None)."""
    if attr in element_attrs:
        return element_attrs[attr], "خودِ view در layout"
    if style_name:
        for chain_name, definition in _style_chain(style_name, config, definitions):
            if attr in definition["items"]:
                where = f"{os.path.relpath(definition['file'], REPO_ROOT)}:{definition['line']}"
                return definition["items"][attr], f"style «{chain_name}» ({where})"
    return None, None


def _theme_chip_attrs(config, definitions):
    """[(نام تم, attribute, مقدار, فایل:خط)] — attributeهای محدودکننده در سطح تم (به همهٔ TextViewها از
    جمله Chip می‌رسند چون theme آخرین fallback حلِ attribute است)."""
    hazards = []
    for style_name, definition in definitions.get(config, {}).items():
        if not style_name.startswith("Theme."):
            continue
        for chain_name, chained in _style_chain(style_name, config, definitions):
            for attr, value in chained["items"].items():
                if attr in CHIP_TEXT_CONSTRAINT_ATTRS and _chip_attribute_hazard(attr, value):
                    where = f"{os.path.relpath(chained['file'], REPO_ROOT)}:{chained['line']}"
                    hazards.append(f"تم «{style_name}» → «{chain_name}» {attr}={value} ({where})")
    return hazards


def _chip_hazards(config: str):
    """همهٔ Chipهای layoutها با مقدارهای ممنوع ⇒ (فهرست مشکلات, تعداد چیپ‌های اسکن‌شده, شمارهٔ چیپ‌های هر فایل)."""
    definitions = _style_definitions()
    problems = []
    scanned = 0
    per_file = {}
    for path in _layout_files():
        relative = os.path.relpath(path, REPO_ROOT)
        source = _read(path)
        for tag, attrs, line in _view_tags(source):
            if tag != CHIP_VIEW_TAG:
                continue
            scanned += 1
            per_file[relative] = per_file.get(relative, 0) + 1
            element_id = attrs.get("android:id", "").split("/")[-1] or f"خط {line}"
            style_ref = attrs.get("style", "")
            style_name = style_ref.split("/")[-1] if style_ref.startswith("@style/") else ""
            for attr in CHIP_TEXT_CONSTRAINT_ATTRS:
                value, origin = _hazard_origin(attr, attrs, style_name, config, definitions)
                if value is not None and _chip_attribute_hazard(attr, value):
                    problems.append(f"{relative}:{line} «{element_id}» → {attr}={value} از {origin}")
    return problems, scanned, per_file


class TestAndroidChipIsNeverMultiLine(unittest.TestCase):
    """گارد ۵ — کرش واقعی «Chip does not support multi-line text» (صفحهٔ مدیریت کلاس‌ها)."""

    def test_5a_no_layout_chip_resolves_to_multi_line_text(self):
        offenders = []
        scanned_total = 0
        for config in ("values", "values-night"):
            problems, scanned, _per_file = _chip_hazards(config)
            scanned_total = max(scanned_total, scanned)
            offenders += [f"[{config}] {problem}" for problem in problems]
        self.assertGreater(scanned_total, 0, "هیچ Chip ای در layoutها اسکن نشد — گارد بی‌اثر است")
        self.assertEqual(
            offenders,
            [],
            "Chip چندخطی ⇒ UnsupportedOperationException در inflate (کرش صفحه):\n" + "\n".join(offenders),
        )

    def test_5b_reported_crash_file_still_has_chips_and_is_scanned(self):
        """قفل رگرسیون: فایلِ گزارش‌شدهٔ کاربر (`item_class_row.xml`) واقعاً چیپ دارد و اسکن می‌شود."""
        _problems, _scanned, per_file = _chip_hazards("values")
        crash_file = "KharazmiAdmin/app/src/main/res/layout/item_class_row.xml"
        self.assertIn(crash_file, per_file, f"فایل ${crash_file} دیگر چیپ ندارد — گارد باید بازبینی شود")
        self.assertEqual(per_file[crash_file], 3, "item_class_row باید ۳ چیپ داشته باشد (پایه/جنسیت/جلسه)")

    def test_5c_theme_level_chip_attributes_are_safe(self):
        offenders = []
        for config in ("values", "values-night"):
            offenders += [f"[{config}] {item}" for item in _theme_chip_attrs(config, _style_definitions())]
        self.assertEqual(
            offenders,
            [],
            "attribute چندخطی در سطح تم ⇒ همهٔ Chipها کرش می‌کنند:\n" + "\n".join(offenders),
        )

    def test_5d_chip_styles_are_explicitly_single_line(self):
        """استایل‌های چیپ باید صریحاً تک‌خطی باشند تا به پیش‌فرض کتابخانه وابسته نباشیم."""
        definitions = _style_definitions()
        for style_name in ("GajChipStyle", "Widget.Kharazmi.DS.Chip", "Widget.Kharazmi.DS.Chip.Tag"):
            definition = definitions["values"].get(style_name)
            self.assertIsNotNone(definition, f"استایل چیپ «{style_name}» پیدا نشد")
            items = definition["items"]
            self.assertEqual(items.get("android:singleLine"), "true", f"{style_name}: singleLine باید true باشد")
            self.assertEqual(items.get("android:maxLines"), "1", f"{style_name}: maxLines باید ۱ باشد")


# ---------------------------------------------------------------------------
# FIX(class-finance-freshness) — گارد ۶: اعداد مالی «اطلاعات کلی» صفحهٔ کلاس نباید snapshot قدیمی بماند
#
# باگ گزارش‌شده (اسکرین‌شات کاربر از کلاس ریاضی ۱۰۰۰۰۲): بعد از برگزاری و ثبت یک جلسه،
# «💰 درآمد وصول شده / ⚠️ بدهی به معلم / ⚠️ بدهی به آموزشگاه» صفر دیده می‌شد، در حالی که
# تب «لیست دانش‌آموزان» (و برگهٔ حضور) همان دو بدهی را غیرصفر نشان می‌داد. چون هر دو endpoint سرور
# از یک تابع می‌خوانند (`calculate_enrollment_debt_breakdown`)، اختلاف فقط می‌تواند از «سنّ داده»
# باشد: گزارش کلاس فقط یک‌بار در onCreate خوانده می‌شد (بدون refresh در بازگشت از «ثبت حضور و غیاب»/
# «ثبت‌نام شاگرد») و کش `class_report_*` هم بعد از ثبت جلسه باطل نمی‌شد ⇒ در fallback آفلاین
# (کش ≤۵ دقیقه) یا نمایش درون‌حافظه‌ای، snapshot قبل از جلسه با همان صفرها نشان داده می‌شد.
# این گارد الزامات fix را قفل می‌کند؛ منطق مالی سرور هیچ تغییری نکرده است.
# ---------------------------------------------------------------------------

def _kotlin_source(file_name: str) -> str:
    path = os.path.join(JAVA_DIR, "com", "example", "kharazmiadmin", file_name)
    return _strip_comments(_read(path))


def _kotlin_function_body(source: str, signature: str) -> str:
    """بدنهٔ یک تابع کاتلین را با تطبیق آکولاد برمی‌گرداند (اسکن فقط همان تابع، نه کل فایل)."""
    index = source.find(signature)
    if index < 0:
        return ""
    opening = source.find("{", index)
    if opening < 0:
        return ""
    depth = 0
    for position in range(opening, len(source)):
        char = source[position]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[opening + 1:position]
    return ""


class TestClassDetailFinanceFreshnessGuard(unittest.TestCase):
    """گارد ۶ — گزارش مالی صفحهٔ کلاس باید در بازگشت به صفحه تازه شود و کش بعد از تغییر مالی باطل شود."""

    def test_6a_class_detail_refetches_report_when_returning_to_screen(self):
        body = _kotlin_function_body(_kotlin_source("ClassDetailActivity.kt"), "override fun onResume()")
        self.assertTrue(body, "onResume در ClassDetailActivity وجود ندارد ⇒ اعداد مالی بعد از "
                              "بازگشت از ثبت حضور/غیاب همچنان snapshot قدیمی می‌مانند")
        self.assertIn("fetchData()", body, "onResume باید گزارش کلاس («اطلاعات کلی») را دوباره بخواند")
        self.assertIn("fetchStudentsFullData()", body, "onResume باید لیست دانش‌آموزان را هم تازه کند")
        self.assertIn("firstResumeHandled", body,
                      "اولین onResume (بلافاصله بعد از onCreate) باید بی‌اثر باشد تا fetch تکراری نزنیم")

    def test_6b_report_refresh_keeps_the_selected_tab(self):
        body = _kotlin_function_body(_kotlin_source("ClassDetailActivity.kt"), "private fun fetchData()")
        self.assertTrue(body, "fetchData در ClassDetailActivity پیدا نشد")
        self.assertIn("updateUI(tabLayout.selectedTabPosition)", body,
                      "بعد از تازه‌سازی، همان تبِ انتخاب‌شده باید رندر شود")
        self.assertNotIn("updateUI(0)", body,
                         "پرش اجباری به تب اول در fetchData ⇒ تازه‌سازی onResume کاربر را از تب جاری بیرون می‌اندازد")

    def test_6c_session_submit_invalidates_the_class_caches(self):
        source = _kotlin_source("AttendanceActivity.kt")
        helper = _kotlin_function_body(source, "private fun invalidateClassCaches(")
        self.assertTrue(helper, "invalidateClassCaches در AttendanceActivity وجود ندارد")
        self.assertIn('"class_report_$courseId"', helper,
                      "کش گزارش کلاس (اعداد «اطلاعات کلی») باید باطل شود")
        self.assertIn('"class_students_full_$courseId"', helper,
                      "کش لیست دانش‌آموزان کلاس هم باید باطل شود")

        direct = _kotlin_function_body(source, "private fun executeSessionSubmissionOnServer(")
        self.assertTrue(direct, "مسیر ثبت آنلاین جلسه پیدا نشد")
        self.assertIn("invalidateClassCaches(data.course_id)", direct,
                      "ثبت/ویرایش موفق جلسه باید کش همان کلاس را باطل کند")
        # بیلد واقعی شکست خورد: SessionSubmitData فیلد classId ندارد (course_id دارد) ⇒ «Unresolved reference».
        # هر `data.<فیلد>` در این تابع باید فیلد واقعی SessionSubmitData باشد.
        fields = set(re.findall(r"val (\w+):", _kotlin_declaration(_kotlin_source("AppModels.kt"), "data class SessionSubmitData(")))
        self.assertEqual(fields, {"course_id", "date", "items"})
        for used in set(re.findall(r"\bdata\.(\w+)", direct)):
            self.assertIn(used, fields, f"data.{used} در SessionSubmitData وجود ندارد ⇒ خطای کامپایل")

        queued = _kotlin_function_body(source, "private suspend fun sendQueueItem(")
        self.assertTrue(queued, "مسیر ارسال صف آفلاین جلسه پیدا نشد")
        self.assertIn("invalidateClassCaches(item.courseId)", queued,
                      "ارسال موفق از صف آفلاین هم مالی کلاس را عوض می‌کند ⇒ کش باید باطل شود")

    def test_6d_payment_success_invalidates_the_class_report_cache(self):
        body = _kotlin_function_body(_kotlin_source("InvoiceActivity.kt"), "private fun sendData(")
        self.assertTrue(body, "sendData در InvoiceActivity پیدا نشد")
        self.assertIn('clearByPrefix(this@InvoiceActivity, "class_report")', body,
                      "هر پرداخت «درآمد وصول شده» و بدهی‌ها را عوض می‌کند ⇒ کش گزارش کلاس باید باطل شود")


# ---------------------------------------------------------------------------
# FIX (تاریخچهٔ جلسات) — گارد ۷: تبِ دومِ صفحهٔ کلاس باید «نامِ» حاضر/غایب‌ها و روزِ هفته را نشان دهد
#
# خواستهٔ کاربر (اسکرین‌شات تبِ «تاریخچه جلسات» کلاس ۱۰۰۰۰۲): قبلاً هر جلسه فقط
# «✅ حاضرین: N نفر / ❌ غایبین: M نفر» بود؛ نه نامِ کسی دیده می‌شد و نه روزِ هفته.
# سمتِ سرور تستِ رفتاریِ مستقل دارد (`test_class_session_history_details.py`)؛ این گاردها
# قراردادِ سمتِ اندروید/اسکیما را قفل می‌کنند چون این‌جا Gradle/JDK نیست و اجرای اپ ممکن نیست.
# ---------------------------------------------------------------------------

def _kotlin_declaration(source: str, signature: str) -> str:
    """متنِ داخل پرانتزهای یک declaration (مثل `data class X(`) را با تطبیقِ پرانتز برمی‌گرداند."""
    index = source.find(signature)
    if index < 0:
        return ""
    opening = source.find("(", index)
    if opening < 0:
        return ""
    depth = 0
    for position in range(opening, len(source)):
        char = source[position]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return source[opening + 1:position]
    return ""


class TestClassDetailSessionHistoryGuard(unittest.TestCase):
    """گارد ۷ — نامِ حاضر/غایب + روزِ هفته در تبِ «تاریخچه جلسات» صفحهٔ کلاس."""

    @classmethod
    def setUpClass(cls):
        cls.source = _kotlin_source("ClassDetailActivity.kt")
        cls.strings = dict(_string_entries(os.path.join(RES_DIR, "values", "strings.xml")))

    def test_7a_session_model_carries_names_weekday_and_cost(self):
        fields = _kotlin_declaration(self.source, "data class ClassSessionHistory(")
        self.assertTrue(fields, "مدل ClassSessionHistory در ClassDetailActivity پیدا نشد")
        for expected in (
            "present_students: List<ClassSessionStudent> = emptyList()",
            "absent_students: List<ClassSessionStudent> = emptyList()",
            'weekday: String = ""',
        ):
            self.assertIn(expected, fields, f"فیلد «{expected}» از مدلِ تاریخچهٔ جلسات حذف شده است")

    def test_7b_student_row_model_has_name_status_and_excused(self):
        fields = _kotlin_declaration(self.source, "data class ClassSessionStudent(")
        self.assertTrue(fields, "مدل ClassSessionStudent در ClassDetailActivity پیدا نشد")
        for expected in ('name: String = ""', 'status: String = "Present"', "excused: Boolean = false"):
            self.assertIn(expected, fields, f"فیلد «{expected}» از مدلِ ردیفِ شاگرد حذف شده است")

    def test_7c_tab_render_prints_student_names_and_weekday(self):
        body = _kotlin_function_body(self.source, "private fun updateUI(")
        self.assertTrue(body, "updateUI در ClassDetailActivity پیدا نشد")
        self.assertIn("R.string.cdetail_hist_summary", body, "خطِ جمعِ دوره (جلسه/حاضر/غایب) حذف شده است")
        self.assertIn("R.string.cdetail_hist_row_weekday", body, "روزِ هفته کنارِ تاریخِ جلسه باید چاپ شود")
        self.assertIn("appendSessionStudents(sb, sess.present_students)", body,
                      "نامِ حاضرینِ هر جلسه باید نوشته شود، نه فقط تعدادشان")
        self.assertIn("appendSessionStudents(sb, sess.absent_students)", body,
                      "نامِ غایبینِ هر جلسه باید نوشته شود، نه فقط تعدادشان")

    def test_7d_student_helper_prints_names_with_late_and_excused_tags(self):
        helper = _kotlin_function_body(self.source, "private fun appendSessionStudents(")
        self.assertTrue(helper, "هلپر appendSessionStudents پیدا نشد")
        for key in ("cdetail_hist_student_row", "cdetail_hist_late_tag", "cdetail_hist_excused_tag"):
            self.assertIn(f"R.string.{key}", helper, f"هلپر باید از رشتهٔ {key} استفاده کند")
        self.assertIn("isBlank()", helper, "نامِ خالی نباید خطِ خالی چاپ کند")

    def test_7e_new_strings_exist_and_weekday_fallback_is_available(self):
        for name in (
            "cdetail_hist_row_weekday", "cdetail_hist_summary", "cdetail_hist_student_row",
            "cdetail_hist_late_tag", "cdetail_hist_excused_tag", "cdetail_hist_cost", "cdetail_hist_time",
        ):
            self.assertIn(name, self.strings, f"رشتهٔ «{name}» در values/strings.xml نیست")
        self.assertIn("JalaliUtils.persianWeekdayName(", self.source,
                      "برای پاسخ/کشِ قدیمیِ بدون weekday باید fallbackِ محلی محاسبه شود")
        jalali = _kotlin_source("JalaliUtils.kt")
        self.assertIn("fun persianWeekdayName(", jalali, "fallbackِ روزِ هفته حذف شده است")

    def test_7f_server_schema_and_report_keep_the_new_fields(self):
        schemas = _read(os.path.join(SERVER_DIR, "schemas.py"))
        self.assertIn("class ClassSessionStudent(BaseModel):", schemas)
        session_schema = schemas.split("class ClassSessionHistory(BaseModel):", 1)[-1].split("class ", 1)[0]
        for expected in ("present_students", "absent_students", "weekday", "total_cost",
                         "cost_per_student", "session_id", "start_time", "end_time"):
            self.assertIn(expected, session_schema, f"فیلد «{expected}» از اسکیمای تاریخچهٔ جلسات حذف شده است")
        routines = _read(os.path.join(SERVER_DIR, "routers", "classes.py"))
        self.assertIn("PERSIAN_DAY_NAMES", routines, "روزِ هفته باید از تقویمِ مرکزیِ سرور بیاید")
        self.assertIn("display_name(", routines, "نامِ حاضر/غایب باید از هلپرِ امنِ نام بیاید")


class TestInvoicePerClassSessionsGuard(unittest.TestCase):
    """گارد ۸ — صدور فیش/حواله: هر کلاس جدا، نام معلم، «برای چند جلسه»، چاپ حواله."""

    @classmethod
    def setUpClass(cls):
        cls.invoice = _kotlin_source("InvoiceActivity.kt")
        cls.labels = _kotlin_source("EnrollmentLabels.kt")
        cls.profile = _kotlin_source("StudentProfileActivity.kt")
        cls.models = _kotlin_source("AppModels.kt")
        cls.api = _kotlin_source("ApiInterfaces.kt")
        cls.strings = dict(_string_entries(os.path.join(RES_DIR, "values", "strings.xml")))
        cls.layout = _read(os.path.join(RES_DIR, "layout", "activity_invoice.xml"))

    def test_8a_layout_has_every_view_the_activity_looks_up(self):
        for view_id in ("tvSessionInfo", "layoutSessions", "etSessionsCount", "tvSessionsHint"):
            self.assertIn(f'@+id/{view_id}', self.layout, f"شناسهٔ {view_id} در activity_invoice.xml نیست ⇒ findViewById کرش می‌کند")
            self.assertIn(f"R.id.{view_id}", self.invoice)
        self.assertLess(self.layout.index("@+id/tvSessionInfo"), self.layout.index("@+id/layoutDebtTeacher"),
                        "«برای چند جلسه» باید بالای ردیف‌های بدهی باشد")

    def test_8b_no_multiline_picker_label_is_used_as_class_name(self):
        """قبلاً برچسب چندخطی (با بدهی‌ها) به‌عنوان نام کلاس روی فرم و حواله می‌رفت."""
        self.assertNotIn("enrollmentLabel(", self.invoice)
        self.assertNotIn("enrollmentLabel(", self.profile)
        self.assertNotIn("pickerLabel(", "\n".join(re.findall(r"loadStudentClassStatus\([^\n]*", self.invoice)))
        for chunk in re.findall(r"openInvoice\([^\n]*", self.profile):
            self.assertNotIn("pickerLabel", chunk)

    def test_8c_picker_label_shows_teacher_name_and_per_class_debts(self):
        body = _kotlin_function_body(self.labels, "fun pickerLabel(")
        self.assertTrue(body, "pickerLabel در EnrollmentLabels نیست")
        self.assertIn("debtTeacherLine(", body)
        self.assertIn("debtInstituteLine(", body)
        self.assertIn("sessionsLine(", body)
        teacher_line = _kotlin_function_body(self.labels, "fun debtTeacherLine(")
        self.assertIn("enroll_label_debt_teacher_named", teacher_line, "نام معلم باید کنار «بدهی به معلم» بیاید")
        self.assertIn("%2$s", self.strings["enroll_label_debt_teacher_named"])

    def test_8d_form_shows_session_info_above_debts_and_flags_stale_server(self):
        body = _kotlin_function_body(self.invoice, "private fun renderClassStatus(")
        self.assertTrue(body, "renderClassStatus پیدا نشد")
        for token in ("tvSessionInfo.text", "invoice_session_info", "invoice_stale_server", "invoice_due_teacher_named"):
            self.assertIn(token, body)
        self.assertIn("sessions_billed == null", body, "سرور/APK قدیمی باید صریح گزارش شود، نه اعداد بی‌صدا")

    def test_8e_admin_session_field_is_admin_only_and_validated(self):
        self.assertRegex(self.invoice, r"layoutSessions\.visibility = View\.VISIBLE")
        self.assertIn("if (isAdmin) etSessionsCount", self.invoice, "فیلد جلسه فقط برای ادمین خوانده شود")
        self.assertIn("parsed < 1 || parsed > 1000", self.invoice)
        self.assertIn("sessions_covered = sessionsCovered", self.invoice, "تعداد جلسه باید به سرور برسد")
        self.assertIn("$sessionsCovered", self.invoice, "تعداد جلسه باید در امضای ضد-دوباره‌ثبتی (formSig) باشد")
        self.assertRegex(self.models, r"class FinanceSubmitData\((?:.|\n)*?sessions_covered: Int\? = null")
        recompute = _kotlin_function_body(self.invoice, "private fun recomputeAmountsFromSessions(")
        self.assertIn("if (!isAdmin) return", recompute)
        self.assertIn("unpaid_session_items", recompute)

    def test_8f_receipt_print_and_pdf_use_server_receipt_fields(self):
        self.assertIn("lastReceipt = d", _kotlin_function_body(self.invoice, "private fun loadAndShowReceipt("))
        html = _kotlin_function_body(self.invoice, "private fun receiptHtmlExtraRows(")
        for token in ("invoice_lbl_teacher", "invoice_lbl_sessions", "invoice_lbl_paid_to", "invoice_lbl_remaining", "htmlEncode"):
            self.assertIn(token, html)
        self.assertIn("receiptHtmlExtraRows()", _kotlin_function_body(self.invoice, "private fun printReceiptClientSide("))
        pdf = _kotlin_function_body(self.invoice, "private fun generatePdfClientSide(")
        for token in ("invoice_pdf_teacher", "invoice_pdf_sessions", "invoice_pdf_paid_to"):
            self.assertIn(token, pdf)

    def test_8g_models_carry_session_fields_as_nullable(self):
        for src, decl in ((self.models, "data class ActiveStudentEnrollment("), (self.models, "data class TeacherFinancialItem("),
                          (self.api, "data class StudentClassStatus(")):
            fields = _kotlin_declaration(src, decl)
            self.assertTrue(fields, f"{decl} پیدا نشد")
            self.assertRegex(fields, r"sessions_billed: Int\? = null", f"{decl} باید sessions_billed nullable داشته باشد")
            self.assertIn("contract_only", fields)
        self.assertIn("unpaid_session_items", _kotlin_declaration(self.api, "data class StudentClassStatus("))

    def test_8h_all_new_strings_exist_and_are_used(self):
        prefixes = ("enroll_label_", "invoice_session", "invoice_sessions_", "invoice_stale_server", "invoice_lbl_teacher",
                    "invoice_lbl_sessions", "invoice_lbl_paid_to", "invoice_lbl_remaining", "invoice_pdf_teacher",
                    "invoice_pdf_sessions", "invoice_pdf_paid_to", "invoice_confirm_class", "invoice_confirm_sessions",
                    "profile_class_", "cdetail_debt_sessions")
        keys = [k for k in self.strings if k.startswith(prefixes)]
        self.assertGreaterEqual(len(keys), 20)
        corpus = "\n".join(_kotlin_source(f) for f in os.listdir(os.path.join(JAVA_DIR, "com", "example", "kharazmiadmin"))
                           if f.endswith(".kt")) + self.layout
        for key in keys:
            self.assertTrue(f"R.string.{key}" in corpus or f"@string/{key}" in corpus, f"رشتهٔ بدون مصرف: {key}")


class TestArchivedClassesRedesignGuard(unittest.TestCase):
    """گارد ۹ — کلاس‌های حذفی: صفحهٔ لیست + جست‌وجوی زنده + صفحهٔ گزارش (به‌جای دیالوگ متنی)."""

    @classmethod
    def setUpClass(cls):
        cls.main = _kotlin_source("MainActivity.kt")
        cls.listing = _kotlin_source("ArchivedClassesActivity.kt")
        cls.detail = _kotlin_source("ArchivedClassDetailActivity.kt")
        cls.models = _kotlin_source("AppModels.kt")
        cls.strings = dict(_string_entries(os.path.join(RES_DIR, "values", "strings.xml")))
        cls.manifest = _read(os.path.join(ANDROID_MAIN, "AndroidManifest.xml"))

    def test_9a_both_screens_registered_and_not_exported(self):
        for name in ("ArchivedClassesActivity", "ArchivedClassDetailActivity"):
            m = re.search(r'<activity\s+android:name="\.%s"[^>]*?/>' % name, self.manifest, re.S)
            self.assertIsNotNone(m, f"{name} در AndroidManifest ثبت نشده ⇒ ActivityNotFoundException")
            self.assertIn('android:exported="false"', m.group(0))

    def test_9b_main_opens_the_new_page_instead_of_the_text_dialog(self):
        self.assertIn("ArchivedClassesActivity::class.java", _kotlin_function_body(self.main, "fun openArchivedClasses("))
        self.assertNotIn("showDeletedClassesDialog", self.main)
        self.assertNotIn("showArchivedClassDetail", self.main)
        self.assertGreaterEqual(self.main.count("openArchivedClasses()"), 3, "منوی کشویی و داشبورد و تعریف تابع")

    def test_9c_list_screen_searches_by_all_four_criteria_live_and_debounced(self):
        for token in ("title =", "teacher =", "code =", "deletedFrom =", "deletedTo ="):
            self.assertIn(token, self.listing, f"فیلتر {token} به API فرستاده نمی‌شود")
        self.assertIn("addTextChangedListener", self.listing)
        self.assertIn("delay(", self.listing, "جست‌وجو باید debounce داشته باشد")
        self.assertIn("requestSeq", self.listing, "پاسخ کهنه نباید نتیجهٔ جدیدتر را بازنویسی کند")
        self.assertIn("EXTRA_COURSE_ID", self.listing)

    def test_9d_api_exposes_the_filters_as_optional_query_params(self):
        body = _kotlin_function_body(self.main, "interface DeletedClassesApi")
        self.assertTrue(body, "DeletedClassesApi پیدا نشد")
        for q in ("query", "title", "teacher", "code", "deleted_from", "deleted_to"):
            self.assertRegex(body, r'@Query\("%s"\) \w+: String\? = null' % q)

    def test_9e_detail_models_are_defaulted_so_old_server_and_legacy_rows_do_not_crash(self):
        for decl in ("data class ArchivedClassDetail(", "data class ArchivedStudentRow(", "data class ArchivedAttendanceTotals(",
                     "data class ArchivedFinanceTotals(", "data class ArchivedSessionRow("):
            fields = _kotlin_declaration(self.models, decl)
            self.assertTrue(fields, f"{decl} پیدا نشد")
            for line in fields.split("@SerializedName")[1:]:
                self.assertIn("=", line, f"فیلد بدون مقدار پیش‌فرض در {decl}: {line.strip()[:60]}")

    def test_9f_detail_screen_renders_every_requested_number(self):
        body = _kotlin_function_body(self.detail, "private fun render(")
        self.assertTrue(body)
        for token in ("at.present", "at.absent.toString()", "at.absentUnexcused", "at.absentExcused",
                      "fin.paid", "fin.debtTotal", "students.size", "studentCard("):
            self.assertIn(token, body, f"{token} در گزارش کلاس حذفی نمایش داده نمی‌شود")
        self.assertLess(body.index("arch_s_students"), body.index("studentCard("), "عدد دانش‌آموزان باید بالای فهرست باشد")

    def test_9g_restore_flow_moved_intact_with_confirm_and_warnings_dialog(self):
        confirm = _kotlin_function_body(self.detail, "private fun confirmRestoreArchivedClass(")
        self.assertIn("main_trash_restore_confirm_msg", confirm)
        self.assertIn("restoreArchivedClass(courseId, includeFinancialHistory.isChecked)", confirm)
        self.assertIn("arch_restore_include_financial", confirm)
        restore = _kotlin_function_body(self.detail, "private fun restoreArchivedClass(")
        self.assertIn("ClassRestoreRequest(includeFinancialHistory = includeFinancialHistory)", restore)
        self.assertIn("financialRestoreAvailable", confirm)
        self.assertIn("arch_restore_include_financial", confirm)
        self.assertIn("warnings", restore)
        self.assertIn("AlertDialog", restore)
        self.assertIn("CancellationException", restore)

    def test_9i_old_server_shows_stale_notice_not_fake_zeros(self):
        body = _kotlin_function_body(self.detail, "private fun render(")
        self.assertIn("d.students == null && d.attendanceTotals == null && d.financeTotals == null", body)
        self.assertIn("R.string.arch_stale_server", body)
        self.assertIn("arch_stale_server", self.strings)

    def test_9h_all_arch_strings_exist_and_are_used(self):
        keys = [k for k in self.strings if k.startswith("arch_")]
        self.assertGreaterEqual(len(keys), 60)
        corpus = "\n".join(_kotlin_source(f) for f in os.listdir(os.path.join(JAVA_DIR, "com", "example", "kharazmiadmin"))
                           if f.endswith(".kt"))
        for name in os.listdir(os.path.join(RES_DIR, "layout")):
            if name.endswith(".xml"):
                corpus += _read(os.path.join(RES_DIR, "layout", name))
        for key in keys:
            self.assertTrue(f"R.string.{key}" in corpus or f"@string/{key}" in corpus, f"رشتهٔ بدون مصرف: {key}")


class TestClassBannerPerClassNoteGuard(unittest.TestCase):
    """گارد ۱۰ — بنر کلاس و ردیف دانش‌آموز: «بدهی بابت چند جلسهٔ همین کلاس» + شمارش حضور همین کلاس."""

    @classmethod
    def setUpClass(cls):
        cls.notes = _kotlin_source("ClassBannerNotes.kt")
        cls.mgmt = _kotlin_source("ClassManagementActivity.kt")
        cls.teacher = _kotlin_source("TeacherDashboardActivity.kt")
        cls.detail = _kotlin_source("ClassDetailActivity.kt")
        cls.models = _kotlin_source("AppModels.kt")
        cls.layout = _read(os.path.join(RES_DIR, "layout", "item_class_row.xml"))
        cls.strings = dict(_string_entries(os.path.join(RES_DIR, "values", "strings.xml")))

    def test_10a_layout_has_note_view_hidden_by_default(self):
        m = re.search(r'<TextView[^>]*@\+id/tvDebtSessionsNote[^>]*>', self.layout, re.S)
        self.assertIsNotNone(m)
        self.assertIn('android:visibility="gone"', m.group(0))

    def test_10b_both_banners_bind_the_note_from_their_own_row(self):
        for src in (self.mgmt, self.teacher):
            self.assertIn("R.id.tvDebtSessionsNote", src)
            self.assertIn("ClassBannerNotes.bindDebtNote(", src)
            self.assertIn("item.unpaid_sessions", src)
            self.assertIn("item.sessions_billed", src)

    def test_10c_models_carry_new_fields_nullable(self):
        for decl in ("data class ClassListItem(", "data class TeacherClassItem("):
            fields = _kotlin_declaration(self.models + self.teacher, decl)
            self.assertRegex(fields, r"unpaid_sessions: Int\? = null", decl)
            self.assertRegex(fields, r"sessions_billed: Int\? = null", decl)

    def test_10d_note_hidden_for_old_server_and_for_no_debt(self):
        body = _kotlin_function_body(self.notes, "fun debtNoteRes(")
        self.assertIn("unpaidSessions == null && sessionsBilled == null", body)
        self.assertIn("return null", body)
        self.assertIn("View.GONE", _kotlin_function_body(self.notes, "fun bindDebtNote("))

    def test_10e_student_row_shows_real_class_counts(self):
        self.assertIn("R.string.cdetail_att_counts", self.detail)
        self.assertIn("fullStudent.present_count", self.detail)
        self.assertIn("fullStudent.total_sessions", self.detail)
        self.assertEqual(len(_placeholders(self.strings["cdetail_att_counts"])), 3)

    def test_10f_strings_exist_with_right_arity(self):
        self.assertEqual(len(_placeholders(self.strings["banner_debt_sessions"])), 1)
        self.assertIn("banner_debt_contract", self.strings)


class TestReportZeroExplanationGuard(unittest.TestCase):
    """گارد ۱۱ — گزارش‌گیری: توضیح «چرا صفر است؟» + ماه جاری دقیق (نه تقریب روز ۲۱)."""

    @classmethod
    def setUpClass(cls):
        cls.report = _kotlin_source("ReportActivity.kt")
        cls.hints = _kotlin_source("ReportHints.kt")
        cls.layout = _read(os.path.join(RES_DIR, "layout", "activity_report.xml"))
        cls.strings = dict(_string_entries(os.path.join(RES_DIR, "values", "strings.xml")))

    def test_11a_layout_has_hint_view_hidden_by_default(self):
        m = re.search(r'<TextView[^>]*@\+id/tvReportHint[^>]*>', self.layout, re.S)
        self.assertIsNotNone(m)
        self.assertIn('android:visibility="gone"', m.group(0))
        self.assertLess(self.layout.index("@+id/tvMonthlyUncollected"), self.layout.index("@+id/tvReportHint"))

    def test_11b_model_is_nullable_for_old_server_and_activity_binds_it(self):
        self.assertRegex(self.report, r"val diagnostics: ReportDiagnostics\? = null")
        self.assertIn("ReportHints.bind(", self.report)
        self.assertIn("summary.diagnostics", self.report)
        self.assertIn("R.id.tvReportHint", self.report)

    def test_11c_hint_logic_never_touches_numbers_and_hides_without_data(self):
        self.assertIn("d == null", self.hints)
        self.assertIn("View.GONE", self.hints)
        self.assertNotIn("Toman", self.hints)
        for key in ("rpt_hint_no_sessions", "rpt_hint_month_empty", "rpt_hint_month_empty_undated", "rpt_hint_zero_share", "rpt_hint_prepaid"):
            self.assertIn(f"R.string.{key}", self.hints)
            self.assertIn(key, self.strings)

    def test_11d_current_month_uses_exact_jalali_converter(self):
        body = _kotlin_function_body(self.report, "private fun setupDateDropdowns(")
        self.assertIn("JalaliUtils.todayJalaliString()", body)
        self.assertNotIn("gd < 21", body, "تقریب قدیمی روز ۲۱ ماه را اشتباه می‌دهد")


if __name__ == "__main__":
    unittest.main()
