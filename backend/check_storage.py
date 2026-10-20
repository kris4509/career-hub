"""Checks that the backend can reach Supabase Storage and that the bucket is private."""
import os

import requests
from dotenv import load_dotenv

load_dotenv()

url = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
key = (os.getenv("SUPABASE_SERVICE_KEY") or "").strip()

if not url or not key:
    raise SystemExit("SUPABASE_URL or SUPABASE_SERVICE_KEY is missing from backend/.env")

# New-style secret keys (sb_secret_...) go in the apikey header only.
# Legacy service_role keys are JWTs and also go in the Authorization header.
headers = {"apikey": key}
if not key.startswith("sb_"):
    headers["Authorization"] = f"Bearer {key}"

response = requests.get(f"{url}/storage/v1/bucket", headers=headers, timeout=20)
print("Status:", response.status_code)

if response.ok:
    for bucket in response.json():
        print(f" - {bucket['name']}  public={bucket['public']}")
else:
    print(response.text[:300])