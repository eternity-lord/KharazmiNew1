"""لایهٔ service — دامنهٔ شعبهٔ کاربر (branch isolation) (REFAC P3a).

چرا این ماژول: `get_user_branch_filter` یک قاعدهٔ **عرضی** است (شعبهٔ مؤثر برای هر
درخواست، بر اساس نقش کاربر و `branch_id` درخواستی) ولی تعریفش وسط `routers/finance.py`
بود و شش روترِ دیگر مجبور بودند برای استفاده از آن **از روترِ مالی** import کنند:

    from routers.finance import get_user_branch_filter   # در admin/analytics/crm/exports/reports/students

یعنی یک وابستگیِ روتر→روتر که هیچ‌کدام از آن‌ها با «مالی» سر و کار ندارند. حالا قاعده
در لایهٔ service است و همهٔ مصرف‌کننده‌ها مستقیم از آنجا می‌گیرند.

کد **بایت‌به‌بایت** منتقل شده و منطق تغییر نکرده. `routers/finance.py` هم آن را import
می‌کند (خودش ۶ بار مصرفش می‌کند) پس مسیر قدیمی `from routers.finance import
get_user_branch_filter` هم برای سازگاریِ تست‌ها/اسکریپت‌ها کار می‌کند.
"""

from sqlalchemy.orm import Session

import models
from models import User


def get_user_branch_filter(db: Session, authorization: str | None, branch_id: int | None) -> int | None:
    if not authorization:
        return branch_id
    try:
        token = authorization.split()[1]
        session = db.query(models.UserSession).filter(models.UserSession.token == token).first()
        if session:
            if session.sub_role in ["student", "parent"]:
                return branch_id
            user = db.query(User).filter(User.id == session.user_id).first()
            if user and user.branch_id is not None:
                return user.branch_id
    except Exception:
        pass
    return branch_id
