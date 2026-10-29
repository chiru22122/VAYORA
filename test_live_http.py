import urllib.request
import json
import time

base_url = "http://127.0.0.1:8000"
email = f"live_tester_{int(time.time())}@vayora.demo"

# 1. Register
print(f"Registering new account: {email}...")
req_data = json.dumps({
    "name": "Live Tester",
    "email": email,
    "password": "Password123!",
    "phone": "+919876543210"
}).encode("utf-8")

req = urllib.request.Request(
    f"{base_url}/api/auth/register",
    data=req_data,
    headers={"Content-Type": "application/json"}
)

t0 = time.time()
with urllib.request.urlopen(req) as resp:
    reg_res = json.loads(resp.read().decode("utf-8"))
    reg_time = time.time() - t0
    token = reg_res.get("access_token", "")
    print(f"  [PASS] Registration completed in {reg_time:.3f}s. Status 200 OK.")
    print(f"  [TOKEN] {token[:30]}...")

# 2. Login
print("Logging in with the newly created account...")
login_data = json.dumps({
    "email": email,
    "password": "Password123!"
}).encode("utf-8")

req = urllib.request.Request(
    f"{base_url}/api/auth/login",
    data=login_data,
    headers={"Content-Type": "application/json"}
)

t0 = time.time()
with urllib.request.urlopen(req) as resp:
    login_res = json.loads(resp.read().decode("utf-8"))
    login_time = time.time() - t0
    token = login_res.get("access_token", "")
    print(f"  [PASS] Login completed in {login_time:.3f}s. Status 200 OK.")

# 3. Authenticated Profile & Wallet Fetch
print("Verifying session token with /api/user & /api/wallet...")
req_user = urllib.request.Request(
    f"{base_url}/api/user",
    headers={"Authorization": f"Bearer {token}"}
)
with urllib.request.urlopen(req_user) as resp:
    user_info = json.loads(resp.read().decode("utf-8"))
    print(f"  [PASS] Current user: {user_info['name']} ({user_info['email']}), ID: {user_info['user_id']}")

req_wallet = urllib.request.Request(
    f"{base_url}/api/wallet",
    headers={"Authorization": f"Bearer {token}"}
)
with urllib.request.urlopen(req_wallet) as resp:
    wallet_info = json.loads(resp.read().decode("utf-8"))
    print(f"  [PASS] Wallet address: {wallet_info['address']}, INR Balance: {wallet_info['inr_balance']}")
    print(f"  [PASS] Token Addresses returned: {list(wallet_info.get('token_addresses', {}).keys())}")

# 4. Fetch /api/wallet/addresses
print("Verifying dedicated token addresses with /api/wallet/addresses...")
req_addrs = urllib.request.Request(
    f"{base_url}/api/wallet/addresses",
    headers={"Authorization": f"Bearer {token}"}
)
with urllib.request.urlopen(req_addrs) as resp:
    addrs_info = json.loads(resp.read().decode("utf-8"))
    for item in addrs_info:
        print(f"  [PASS] {item['symbol']} ({item['network']}): {item['address']}")

print("\n>>> ALL REGISTRATION, LOGIN, TOKEN ADDRESSES, AND SYSTEM OPERATIONS WORK PERFECTLY! <<<")

