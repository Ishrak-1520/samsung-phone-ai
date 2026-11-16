import os
import subprocess
import sys
import time
import requests

PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_DIR)
os.chdir(PROJECT_DIR)

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

python_bin = os.path.join(PROJECT_DIR, "venv", "Scripts", "python.exe")
BASE_URL = "http://127.0.0.1:8000"


def run_tests():
    server = subprocess.Popen(
        [python_bin, "-m", "uvicorn", "api.main:app", "--port", "8000"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(3)

    try:
        print("API verification")

        print("1. GET /")
        r = requests.get(f"{BASE_URL}/")
        print(f"Status: {r.status_code}")
        print(f"Response: {r.json()}")

        print("2. POST /ask")
        payload_ask = {"question": "What are the camera specs of the Samsung Galaxy S23?"}
        r = requests.post(f"{BASE_URL}/ask", json=payload_ask)
        print(f"Status: {r.status_code}")
        print(f"Response: {r.json()}")

        print("3. GET /review/Samsung Galaxy S23")
        r = requests.get(f"{BASE_URL}/review/Samsung%20Galaxy%20S23")
        print(f"Status: {r.status_code}")
        print(f"Phone: {r.json().get('phone')}")
        print(f"Length: {len(r.json().get('review', ''))} characters")
        print(f"Preview:\n{r.json().get('review', '')[:300]}...\n")

        print("4. POST /compare")
        payload_comp = {"phone1": "Samsung Galaxy S23", "phone2": "Samsung Galaxy S22"}
        r = requests.post(f"{BASE_URL}/compare", json=payload_comp)
        print(f"Status: {r.status_code}")
        print(f"Phone 1: {r.json().get('phone1')}, Phone 2: {r.json().get('phone2')}")
        print(f"Length: {len(r.json().get('comparison', ''))} characters")
        print(f"Preview:\n{r.json().get('comparison', '')[:300]}...\n")

        print("5. GET /review/iPhone 15 (expect 404)")
        r = requests.get(f"{BASE_URL}/review/iPhone%2015")
        print(f"Status: {r.status_code}")
        print(f"Response: {r.json()}")

    finally:
        server.terminate()
        server.wait()
        print("Uvicorn server stopped cleanly.")


if __name__ == "__main__":
    run_tests()

