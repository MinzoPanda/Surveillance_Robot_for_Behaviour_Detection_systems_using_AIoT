import time
import requests

# --- BLYNK CONFIGURATION ---
# Replace with your actual information from Blynk.Console
BLYNK_AUTH = "aoaEO3E5PLfZlZz1AUOMWk7-BcnCVBH2"
EVENT_CODE = "loitering_detected"  # Must match the code in your 'Events' tab


def send_test_notification():
    """Triggers the Blynk event via HTTPS API"""
    print(f"[{time.strftime('%H:%M:%S')}] Attempting to send notification...")

    # Blynk API URL for triggering events
    url = f"https://blynk.cloud/external/api/logEvent?token={BLYNK_AUTH}&code={EVENT_CODE}"

    try:
        response = requests.get(url)
        if response.status_code == 200:
            print(">>> Success! Check your phone now.")
        elif response.status_code == 400:
            print(">>> Error 400: Check your Event Code spelling!")
        elif response.status_code == 401:
            print(">>> Error 401: Invalid Auth Token!")
        else:
            print(f">>> Failed with status code: {response.status_code}")
    except Exception as e:
        print(f">>> Network Error: {e}")


# --- MAIN LOOP ---
print("--- Notification Connection Test Started ---")
print("This will send an alert every 30 seconds. Press Ctrl+C to stop.")

try:
    while True:
        send_test_notification()
        time.sleep(30)  # Wait 30 seconds between tests to avoid spamming
except KeyboardInterrupt:
    print("\n--- Test Stopped by User ---")