"""
FIX(search) — GET /students/search_simple: چندفیلدی، چندکلمه‌ای، case-insensitive، branch isolation

مشکلات اثبات‌شده (regression test این فیکس):
  - فقط last_name و national_code جست‌وجو می‌شد (first_name/نام کامل/student_code/mobile نه)
  - trim/normalize نبود؛ case-sensitivity در PostgreSQL؛ بدون limit؛ بدون branch isolation
  - Android id را از متن نمایشی parse می‌کرد (id فیلد واقعی response بود/می‌ماند)

اجرا:
    cd /home/user/KharazmiApp && export JWT_SECRET_KEY=test \
        && python3 -m pytest Kharazmi_Server/test_student_search_simple.py -q
"""
import datetime
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from dependencies import get_db, hash_password
from main import app
from models import Base, Branch, Student, User, UserSession


class SearchSimpleBase(unittest.TestCase):

    def setUp(self):
        # دیتابیس موقت ایزوله (in-memory) — الگوی تست‌های موجود پروژه
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

        def override_get_db():
            try:
                yield self.db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

        self.db.add_all([
            Branch(id=1, name="شعبه یک", active=True),
            Branch(id=2, name="شعبه دو", active=True),
        ])
        self.db.commit()

        self.db.add_all([
            User(id=1, username="09120000000", password=hash_password("123"), full_name="GlobalAdmin",
                 role="admin", sub_role="admin", branch_id=None),
            User(id=2, username="09121111111", password=hash_password("123"), full_name="Sec1",
                 role="admin", sub_role="secretary", branch_id=1),
            User(id=3, username="09122222222", password=hash_password("123"), full_name="Sec2",
                 role="admin", sub_role="secretary", branch_id=2),
            User(id=4, username="09123333333", password=hash_password("123"), full_name="LegacyTeacher",
                 role="teacher", sub_role="teacher", branch_id=None),
            User(id=5, username="09124444444", password=hash_password("123"), full_name="Student",
                 role="student", sub_role="student", branch_id=None),
        ])
        self.db.commit()
        self.db.add_all([
            UserSession(token="tok_admin_global", user_id=1, sub_role="admin", created_at=datetime.datetime.now()),
            UserSession(token="tok_sec1", user_id=2, sub_role="secretary", created_at=datetime.datetime.now()),
            UserSession(token="tok_sec2", user_id=3, sub_role="secretary", created_at=datetime.datetime.now()),
            UserSession(token="tok_teacher_nb", user_id=4, sub_role="teacher", created_at=datetime.datetime.now()),
            UserSession(token="tok_student", user_id=5, sub_role="student", created_at=datetime.datetime.now()),
        ])
        self.db.commit()

    def tearDown(self):
        app.dependency_overrides.clear()
        try:
            self.db.close()
        finally:
            Base.metadata.drop_all(bind=self.engine)
            self.engine.dispose()

    # ---------- helpers ----------

    _seq = 0

    def _student(self, first_name, last_name, branch_id=1, mobile="09120000000", **kw):
        SearchSimpleBase._seq += 1
        n = SearchSimpleBase._seq
        st = Student(
            first_name=first_name,
            last_name=last_name,
            national_code=kw.pop("national_code", f"1000000{n:03d}"),
            student_mobile=mobile if mobile is not None else f"091299{n:06d}",
            student_code=kw.pop("student_code", 100000 + n),
            birth_date="1390/01/01",
            parent_mobile="09120000000",
            home_phone="0211",
            address="تهران",
            study_status="فعال",
            gender="male",
            branch_id=branch_id,
            is_deleted=kw.pop("is_deleted", False),
            is_suspended=kw.pop("is_suspended", False),
        )
        self.db.add(st)
        self.db.commit()
        self.db.expire_all()
        return self.db.query(Student).filter(Student.id == st.id).first()

    def _search(self, query, token="tok_sec1"):
        return self.client.get(
            "/students/search_simple",
            params={"query": query},
            headers={"Authorization": f"Bearer {token}"},
        )

    def _ids(self, res):
        self.assertEqual(res.status_code, 200, res.text)
        return [r["id"] for r in res.json()]

    def _check(self, res):
        self.assertEqual(res.status_code, 200, res.text)
        return res.json()


class TestSearchFields(SearchSimpleBase):

    def test_search_first_name(self):
        st = self._student("علی", "رضایی")
        self.assertIn(st.id, self._ids(self._search("علی")))
        st2 = self._student("سارا", "رضایی")
        self.assertNotIn(st2.id, self._ids(self._search("علی")))

    def test_search_last_name(self):
        st = self._student("علی", "رضایی")
        self.assertIn(st.id, self._ids(self._search("رضایی")))

    def test_search_full_name(self):
        self._student("علی", "رضایی")
        other = self._student("علی", "محمدی")
        res = self._search("علی رضایی")
        body = self._check(res)
        self.assertIn("علی رضایی", [r["name"].split(" (")[0] for r in body])
        self.assertNotIn(other.id, [r["id"] for r in body])

    def test_search_partial_name(self):
        st = self._student("محمدعلی", "رضایینژاد")
        self.assertIn(st.id, self._ids(self._search("محمد")))
        self.assertIn(st.id, self._ids(self._search("نژاد")))

    def test_search_national_code(self):
        st = self._student("علی", "رضایی", national_code="1111222233")
        self.assertIn(st.id, self._ids(self._search("1111222233")))
        self.assertIn(st.id, self._ids(self._search("2222")))

    def test_search_student_code(self):
        st = self._student("علی", "رضایی", student_code=154321)
        self.assertIn(st.id, self._ids(self._search("154321")))

    def test_search_student_mobile(self):
        st = self._student("علی", "رضایی", mobile="09125557799")
        self.assertIn(st.id, self._ids(self._search("09125557799")))
        # شکل بدون ۰ اول هم باید بزند
        self.assertIn(st.id, self._ids(self._search("9125557799")))

    def test_query_trimmed_and_collapsed(self):
        st = self._student("علی", "رضایی")
        self.assertIn(st.id, self._ids(self._search("  علی رضایی  ")))
        self.assertIn(st.id, self._ids(self._search("علی    رضایی")))  # چند فاصله بین کلمات

    def test_persian_and_case_insensitive_ascii(self):
        st_fa = self._student("مریم", "کریمی")
        st_en = self._student("Ali", "Smith")
        self.assertIn(st_fa.id, self._ids(self._search("مریم")))
        # case-insensitive (سازگار PostgreSQL: func.lower + LIKE)
        self.assertIn(st_en.id, self._ids(self._search("ali")))
        self.assertIn(st_en.id, self._ids(self._search("ALI")))
        self.assertIn(st_en.id, self._ids(self._search("ali smith")))

    def test_empty_and_short_query_returns_empty(self):
        self._student("علی", "رضایی")
        for q in ("", "   ", "ا", "a "):
            res = self._search(q)
            self.assertEqual(res.status_code, 200, res.text)
            self.assertEqual(res.json(), [], f"query {q!r} باید خالی برگردد")

    def test_response_contract_unchanged(self):
        st = self._student("علی", "رضایی", national_code="1111222233")
        res = self._search("علی")
        body = self._check(res)
        row = next(r for r in body if r["id"] == st.id)
        self.assertEqual(set(row.keys()), {"id", "name"})
        self.assertIsInstance(row["id"], int)
        self.assertEqual(row["name"], "علی رضایی (1111222233)")


class TestSearchSafety(SearchSimpleBase):

    def test_deleted_excluded(self):
        st = self._student("علی", "رضایی", is_deleted=True)
        self.assertNotIn(st.id, self._ids(self._search("علی")))

    def test_suspended_excluded(self):
        st = self._student("علی", "رضایی", is_suspended=True)
        self.assertNotIn(st.id, self._ids(self._search("علی")))

    def test_other_branch_not_visible(self):
        """isolation: منشی شعبه ۱، شاگردان شعبه ۲ را نمی‌بیند."""
        b1 = self._student("علی", "رضایی", branch_id=1)
        b2 = self._student("علی", "رضایی", branch_id=2, mobile="09128887766")
        res = self._search("علی", token="tok_sec1")
        body = self._check(res)
        ids = [r["id"] for r in body]
        self.assertIn(b1.id, ids)
        self.assertNotIn(b2.id, ids, "شاگرد شعبهٔ دیگر نباید نمایش داده شود")

    def test_null_branch_not_leaked_to_branch_user(self):
        """branch=NULL legacy برای کاربر شعبه‌دار نشت نمی‌کند (بدون fallback حدسی)."""
        nb = self._student("علی", "رضایی", branch_id=None, mobile="09127776655")
        body = self._check(self._search("علی", token="tok_sec1"))
        self.assertNotIn(nb.id, [r["id"] for r in body])

    def test_no_branch_non_admin_gets_empty(self):
        """معلم legacy بدون شعبه: scope مشخص نیست → نتیجه خالی (نشت داده ممنوع)."""
        self._student("علی", "رضایی", branch_id=1)
        nb = self._student("علی", "رضایی", branch_id=None, mobile="09126665544")
        body = self._check(self._search("علی", token="tok_teacher_nb"))
        self.assertEqual(body, [], "کاربر بدون branch نباید داده بگیرد (حتی رکوردهای NULL)")
        # اما خودِ شاگرد NULL-branch هم از او پنهان است (نه حدس، نه «همان‌شعبه‌ها»)
        self.assertNotIn(nb.id, [r["id"] for r in body])

    def test_global_admin_sees_all(self):
        """policy فعلی ادمین بدون شعبه: دیدن همه (دست‌نخورده)."""
        b1 = self._student("علی", "رضایی", branch_id=1)
        b2 = self._student("علی", "رضایی", branch_id=2, mobile="09125554433")
        nb = self._student("علی", "رضایی", branch_id=None, mobile="09124443322")
        ids = self._ids(self._search("علی", token="tok_admin_global"))
        for s in (b1, b2, nb):
            self.assertIn(s.id, ids)

    def test_student_role_forbidden(self):
        """403 برای شاگرد/ولی (رفتار L14/Y1 دست‌نخورده)."""
        res = self._search("علی", token="tok_student")
        self.assertEqual(res.status_code, 403)

    def test_limit_20(self):
        for i in range(25):
            self._student("علی", f"رضایی{i}", mobile=f"091230000{i:02d}")
        body = self._check(self._search("علی"))
        self.assertLessEqual(len(body), 20, "بیش از ۲۰ نتیجه نباید برگردد")
        self.assertEqual(len(body), 20)


if __name__ == "__main__":
    unittest.main(verbosity=2)
