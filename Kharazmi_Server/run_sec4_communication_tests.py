import httpx
import sys
import os
import json

URL_BASE = "http://localhost:8000"

def run_tests():
    print("=========================================================================")
    print("📱 SECTION 4: COMMUNICATIONS & PARENT PORTAL (E2E)")
    print("=========================================================================")

    # 1. Update Student 2 parent mobile to '09120000003' to trigger Multi-Child login!
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    engine = create_engine("sqlite:///gaj_db.db")
    Session = sessionmaker(bind=engine)
    db = Session()
    db.execute(text("UPDATE students SET parent_mobile = '09120000003' WHERE id = 2;"))
    db.commit()
    db.close()
    print("   [DB Update] Seeded parent 09120000003 with 2 children (Student 1 and Student 2).")

    # 2. Parent OTP Request (First attempt)
    print("\n2. Parent requests OTP (First attempt):")
    res_otp1 = httpx.post(f"{URL_BASE}/parent/request_otp", json={"mobile": "09120000003"})
    print(f"   Status Code: {res_otp1.status_code}")
    print(f"   Response: {json.dumps(res_otp1.json(), indent=2, ensure_ascii=False)}")

    # 3. Parent OTP Request (Second attempt within 60 seconds -> Rate Limit Check!)
    print("\n3. Parent requests OTP (Second attempt - expecting 429 Rate Limit):")
    res_otp2 = httpx.post(f"{URL_BASE}/parent/request_otp", json={"mobile": "09120000003"})
    print(f"   Status Code: {res_otp2.status_code} (Expected: 429)")
    print(f"   Response: {json.dumps(res_otp2.json(), indent=2, ensure_ascii=False)}")

    # 4. Multi-Child Login & IDOR Verification
    print("\n4. Multi-Child OTP Verification & Login:")
    db = Session()
    otp_row = db.execute(text("SELECT otp FROM parent_otps WHERE mobile = '09120000003' ORDER BY id DESC LIMIT 1;")).first()
    db.close()
    
    if otp_row:
        otp_code = otp_row[0]
        print(f"   [DB Query] Retrieved active OTP code from DB: {otp_code}")
        
        # Verify and login -> expect multiple_children=True and temp_token!
        res_login = httpx.post(f"{URL_BASE}/parent/login", json={"mobile": "09120000003", "otp": otp_code})
        print(f"   Status Code: {res_login.status_code}")
        print(f"   Response: {json.dumps(res_login.json(), indent=2, ensure_ascii=False)}")
        temp_token = res_login.json().get("temp_token")
        
        # IDOR Check: Parent attempts to select Student 99 (not their child)
        print("\n   A) Parent tries to select Student 99 (IDOR check - expecting 403/404):")
        res_idor = httpx.post(f"{URL_BASE}/parent/select_child", json={"student_id": 99, "temp_token": temp_token})
        print(f"      Status Code: {res_idor.status_code} (Expected: 403 or 404)")
        print(f"      Response: {json.dumps(res_idor.json(), indent=2, ensure_ascii=False)}")

        # Successful Selection: Select Student 2 (their valid child)
        print("\n   B) Parent selects their valid child (Student 2):")
        res_select = httpx.post(f"{URL_BASE}/parent/select_child", json={"student_id": 2, "temp_token": temp_token})
        print(f"      Status Code: {res_select.status_code} (Expected: 200)")
        print(f"      Response: {json.dumps(res_select.json(), indent=2, ensure_ascii=False)}")
    else:
        print("   ❌ Error: OTP record not found in DB!")

if __name__ == "__main__":
    run_tests()
