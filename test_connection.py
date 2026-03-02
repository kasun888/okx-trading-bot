"""
🔍 IG Login Debug Test
"""
import os
import requests

print("=" * 50)
print("🔍 IG LOGIN DEBUG")
print("=" * 50)

username   = os.environ.get("IG_USERNAME", "")
password   = os.environ.get("IG_PASSWORD", "")
api_key    = os.environ.get("IG_API_KEY", "")
acc_number = os.environ.get("IG_ACC_NUMBER", "")

print(f"\nIG_USERNAME:   '{username}'")
print(f"IG_PASSWORD:   '{password[:2]}****{password[-2:]}' (len={len(password)})")
print(f"IG_API_KEY:    '{api_key[:4]}****' (len={len(api_key)})")
print(f"IG_ACC_NUMBER: '{acc_number}'")

# Test Demo Login
print("\n--- Testing DEMO login ---")
url = "https://demo-api.ig.com/gateway/deal/session"
headers = {
    "X-IG-API-KEY": api_key,
    "Content-Type": "application/json; charset=UTF-8",
    "Accept":       "application/json; charset=UTF-8",
    "Version":      "2"
}
payload = {
    "identifier":        username,
    "password":          password,
    "encryptedPassword": False
}
try:
    r = requests.post(url, headers=headers, json=payload, timeout=15)
    print(f"Status: {r.status_code}")
    print(f"Response: {r.text[:500]}")
except Exception as e:
    print(f"Error: {e}")

print("=" * 50)
