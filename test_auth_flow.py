import time
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

print("Testing health endpoint...")
t0 = time.time()
res = client.get("/api/health")
print(f"Health status: {res.status_code}, time: {time.time()-t0:.3f}s")
assert res.status_code == 200

test_email = f"speedtest_{int(time.time())}@vayora.demo"
print(f"Testing registration for {test_email}...")
t0 = time.time()
res = client.post("/api/auth/register", json={
    "name": "Speed Test User",
    "email": test_email,
    "password": "Password123!",
    "phone": "+1234567890"
})
t_reg = time.time() - t0
print(f"Register status: {res.status_code}, time: {t_reg:.3f}s")
if res.status_code != 200:
    print("Register error response:", res.text)
assert res.status_code == 200, f"Registration failed with {res.status_code}"

print("Testing login...")
t0 = time.time()
res = client.post("/api/auth/login", json={
    "email": test_email,
    "password": "Password123!"
})
t_login = time.time() - t0
print(f"Login status: {res.status_code}, time: {t_login:.3f}s")
if res.status_code != 200:
    print("Login error response:", res.text)
assert res.status_code == 200, f"Login failed with {res.status_code}"
data = res.json()
token = data.get("access_token")
print("Login successful! Got token:", token[:20] if token else None)

print("Testing authenticated user profile...")
t0 = time.time()
res = client.get("/api/user", headers={"Authorization": f"Bearer {token}"})
print(f"Profile status: {res.status_code}, time: {time.time()-t0:.3f}s")
assert res.status_code == 200

print("Testing wallet details...")
t0 = time.time()
res = client.get("/api/wallet", headers={"Authorization": f"Bearer {token}"})
print(f"Wallet status: {res.status_code}, time: {time.time()-t0:.3f}s")
assert res.status_code == 200

print("ALL AUTH AND DASHBOARD FLOW TESTS PASSED!")
