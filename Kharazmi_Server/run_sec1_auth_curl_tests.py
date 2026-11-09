import httpx
import sys
import os
import json

# Connection configuration
URL_BASE = "http://localhost:8000"

def run_tests():
    print("=========================================================================")
    print("🔒 SECTION 1: AUTHENTICATION & ACCESS CONTROL (CURL-BASED E2E)")
    print("=========================================================================")

    # 1. Admin Login
    print("1. Admin Login (09120000000 / 123):")
    login_admin_payload = {"mobile": "09120000000", "password": "123"}
    res_admin = httpx.post(f"{URL_BASE}/auth/login", json=login_admin_payload)
    print(f"   Status Code: {res_admin.status_code}")
    print(f"   Response: {json.dumps(res_admin.json(), indent=2, ensure_ascii=False)}")
    admin_token = res_admin.json().get("token")

    # 2. Secretary Login
    print("\n2. Secretary Login (09121111111 / 123):")
    login_sec_payload = {"mobile": "09121111111", "password": "123"}
    res_sec = httpx.post(f"{URL_BASE}/auth/login", json=login_sec_payload)
    print(f"   Status Code: {res_sec.status_code}")
    print(f"   Response: {json.dumps(res_sec.json(), indent=2, ensure_ascii=False)}")
    sec_token = res_sec.json().get("token")

    # 3. Teacher Login
    print("\n3. Teacher Login (09123333333 / 123):")
    login_teacher_payload = {"mobile": "09123333333", "password": "123"}
    res_teacher = httpx.post(f"{URL_BASE}/auth/login", json=login_teacher_payload)
    print(f"   Status Code: {res_teacher.status_code}")
    print(f"   Response: {json.dumps(res_teacher.json(), indent=2, ensure_ascii=False)}")
    teacher_token = res_teacher.json().get("token")

    # 4. Parent OTP Request & Login
    print("\n4. Parent OTP Request & Login (09120000003):")
    res_parent_otp = httpx.post(f"{URL_BASE}/parent/request_otp", json={"mobile": "09120000003"})
    print(f"   Request OTP Status Code: {res_parent_otp.status_code}")
    print(f"   Request OTP Response: {json.dumps(res_parent_otp.json(), indent=2, ensure_ascii=False)}")

    # Fetch OTP from Database
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    engine = create_engine("sqlite:///gaj_db.db")
    Session = sessionmaker(bind=engine)
    db = Session()
    otp_row = db.execute(text("SELECT otp FROM parent_otps WHERE mobile = '09120000003' ORDER BY id DESC LIMIT 1;")).first()
    db.close()
    
    if otp_row:
        otp_code = otp_row[0]
        print(f"   [DB Query] Retrieved active OTP code from DB: {otp_code}")
        
        # Parent login
        res_parent_login = httpx.post(f"{URL_BASE}/parent/login", json={"mobile": "09120000003", "otp": otp_code})
        print(f"   Parent Login Status Code: {res_parent_login.status_code}")
        print(f"   Parent Login Response: {json.dumps(res_parent_login.json(), indent=2, ensure_ascii=False)}")
    else:
        print("   ❌ Error: OTP record not found in DB!")

    # 5. Access Control Validation (Authorized vs Unauthorized)
    print("\n5. Access Control Validation (SaaS Scope):")
    
    # Authorized: Admin calls POST /branches (manage branches)
    print("   A) Admin calls GET /branches (Authorized):")
    res_branches_admin = httpx.get(f"{URL_BASE}/branches", headers={"Authorization": f"Bearer {admin_token}"})
    print(f"      Status Code: {res_branches_admin.status_code} (Expected: 200)")

    # Unauthorized: Teacher calls POST /branches
    print("   B) Teacher calls POST /branches (Unauthorized - Role Clash):")
    res_branches_teacher = httpx.post(f"{URL_BASE}/branches", json={"name": "شعبه شمال"}, headers={"Authorization": f"Bearer {teacher_token}"})
    print(f"      Status Code: {res_branches_teacher.status_code} (Expected: 403)")

    # Unauthorized: Public / No token calls GET /branches
    print("   C) Public / No token calls GET /branches (Unauthorized - No Token):")
    res_branches_no_token = httpx.get(f"{URL_BASE}/branches")
    print(f"      Status Code: {res_branches_no_token.status_code} (Expected: 401)")

if __name__ == "__main__":
    run_tests()
