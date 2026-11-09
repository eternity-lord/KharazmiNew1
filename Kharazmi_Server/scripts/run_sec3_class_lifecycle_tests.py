import httpx
import sys
import os
import json

URL_BASE = "http://localhost:8000"

def run_tests():
    print("=========================================================================")
    print("🎓 SECTION 3: CLASS LIFECYCLE & SCHEDULING (E2E)")
    print("=========================================================================")
    
    # Clean up any existing conflicting course MATH12 feshly
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    engine = create_engine("sqlite:///gaj_db.db")
    Session = sessionmaker(bind=engine)
    db = Session()
    db.execute(text("DELETE FROM courses WHERE title = 'دیفرانسیل دوازدهم';"))
    db.commit()
    db.close()

    token = "test_admin_token"
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create Class (MATH12) - Incomplete State (0 students)
    print("1. Creating Class (MATH12) - Incomplete state:")
    course_payload = {
        "title": "دیفرانسیل دوازدهم",
        "code": "MATH12",
        "teacher_id": 3,  # teacher id we created
        "education_type": "کنکور",
        "grade_level": "دبیرستان",
        "gender_type": "مختلط",
        "class_type": "خصوصی",
        "days_of_week": "یکشنبه",
        "class_time": "14:00",
        "teacher_session_price": 200000,
        "rule_prepay_teacher": False,
        "rule_prepay_institute": False,
        "rule_calc_absent": True,
        "bg_color": "#FFCC00"
    }
    res_create = httpx.post(f"{URL_BASE}/classes/create", json=course_payload, headers=headers)
    print(f"   Create Class Status: {res_create.status_code}")
    print(f"   Response: {json.dumps(res_create.json(), indent=2, ensure_ascii=False)}")
    course_id = res_create.json().get("id")

    # 2. Approve Class by Admin (Verify approving)
    print("\n2. Admin approves the Class:")
    res_approve = httpx.post(f"{URL_BASE}/admin/approve_class/{course_id}", headers=headers)
    print(f"   Approve Class Status: {res_approve.status_code}")
    print(f"   Response: {json.dumps(res_approve.json(), indent=2, ensure_ascii=False)}")

    # 3. Add Student to Class (Completing Enrollment)
    print("\n3. Adding Student 2 (بهنام) to Class (MATH12):")
    enroll_payload = {
        "student_id": 2,
        "course_id": course_id,
        "register_date": "1405/01/01",
        "shift": "عصر",
        "total_tuition": 1000000,
        "paid_amount": 0,
        "payment_method": "نقدی",
        "receiver": "منشی",
        "discount_type": "none",
        "discount_value": 0
    }
    res_enroll = httpx.post(f"{URL_BASE}/enrollments/add", json=enroll_payload, headers=headers)
    print(f"   Enroll Student Status: {res_enroll.status_code}")
    print(f"   Response: {json.dumps(res_enroll.json(), indent=2, ensure_ascii=False)}")

    # 4. Suspend Class
    print("\n4. Suspending the Class:")
    res_suspend = httpx.post(f"{URL_BASE}/classes/{course_id}/suspend", headers=headers)
    print(f"   Suspend Class Status: {res_suspend.status_code}")
    print(f"   Response: {json.dumps(res_suspend.json(), indent=2, ensure_ascii=False)}")

    # 5. Conflict Check (Clashing schedule)
    print("\n5. Scheduling Conflict Checks:")
    conflict_payload = {
        "teacher_id": 3,               # same teacher!
        "room_id": 1,
        "days_of_week": "یکشنبه",       # same day!
        "class_time": "14:00",          # same time!
        "student_ids": [2]
    }
    res_conf = httpx.post(f"{URL_BASE}/calendar/check_conflicts", json=conflict_payload, headers=headers)
    print(f"   Conflict Check Status: {res_conf.status_code}")
    print(f"   Conflict Check Response: {json.dumps(res_conf.json(), indent=2, ensure_ascii=False)}")

if __name__ == "__main__":
    run_tests()
