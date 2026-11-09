# conftest.py — پیکربندی مشترک سوئیت تست (پوشهٔ Kharazmi_Server/tests)
#
# چرا لازم است:
#   تست‌ها با نام‌های کوتاه، ماژول‌های سرور را import می‌کنند (`import models`، `from main import app`,
#   `import storage`، `import portal_data` و ...). این ماژول‌ها یک پوشه بالاتر (Kharazmi_Server/)
#   هستند. pytest در حالت پیش‌فرض فقط پوشهٔ خودِ فایل تست (همین `tests/`) را به sys.path اضافه
#   می‌کند؛ پس این conftest پوشهٔ سرور را صریحاً اضافه می‌کند تا اجرای تست‌ها از **هر پوشه‌ای**
#   (ریشهٔ ریپو، داخل tests/، داخل Kharazmi_Server/ یا CI) یکسان کار کند.
#
# نکته: هیچ تغییری در منطق برنامه اینجا انجام نمی‌شود؛ فقط مسیر import تثبیت می‌شود.
import os
import sys

SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # .../Kharazmi_Server
if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)
