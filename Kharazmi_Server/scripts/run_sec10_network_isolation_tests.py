import httpx
import json

URL_BASE = "http://localhost:8000"

def run_tests():
    print("=========================================================================")
    print("🛡️ SECTION 10: CLOUDFLARE QUICK TUNNEL NETWORK ISOLATION (E2E)")
    print("=========================================================================")

    # 1. Simulate Local traffic (Android app / local network)
    # Target: /auth/login with Host: localhost:8000
    print("1. Simulating local network traffic (Host: localhost:8000) on /auth/login:")
    res_local = httpx.post(f"{URL_BASE}/auth/login", json={"mobile": "09120000000", "password": "wrong"}, headers={"Host": "localhost:8000"})
    print(f"   Status Code: {res_local.status_code} (Expected: 400 - since wrong password, NOT 404!)")
    print(f"   Response snippet: {res_local.text[:100]}...")

    # 2. Simulate Public Cloudflare Tunnel traffic on non-parent route
    # Target: /auth/login with Host: gaj-portal.trycloudflare.com (unauthorized path)
    print("\n2. Simulating public Cloudflare Tunnel traffic (Host: gaj-portal.trycloudflare.com) on /auth/login:")
    res_public_fail = httpx.post(f"{URL_BASE}/auth/login", json={"mobile": "09120000000", "password": "123"}, headers={"Host": "gaj-portal.trycloudflare.com"})
    print(f"   Status Code: {res_public_fail.status_code} (Expected: 404)")
    print(f"   Response text: {res_public_fail.text}")

    # 3. Simulate Public Cloudflare Tunnel traffic on parent route
    # Target: /parent/portal with Host: gaj-portal.trycloudflare.com (authorized path)
    print("\n3. Simulating public Cloudflare Tunnel traffic (Host: gaj-portal.trycloudflare.com) on /parent/portal:")
    res_public_ok = httpx.get(f"{URL_BASE}/parent/portal", headers={"Host": "gaj-portal.trycloudflare.com"})
    print(f"   Status Code: {res_public_ok.status_code} (Expected: 200)")
    print(f"   Response snippet: {res_public_ok.text[:150]}...")

if __name__ == "__main__":
    run_tests()
