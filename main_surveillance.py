import BlynkLib
import cv2
import os
import time
import threading
import requests
from datetime import datetime
from ultralytics import YOLO

# --- 1. DYNAMIC PATH RESOLUTION (CRITICAL FOR STANDALONE) ---
# This ensures the script finds its files even when run from a .bat file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, 'runs', 'detect', 'train', 'weights', 'best.pt')
DATA_DIR = os.path.join(BASE_DIR, 'security_data', 'intruders')

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# --- 2. CONFIGURATION & CREDENTIALS ---
BLYNK_AUTH = 'aoaEO3E5PLfZlZz1AUOMWk7-BcnCVBH2'
TELEGRAM_TOKEN = '8164442789:AAF7YyAoHUiaacxXzzVeRCsS10ZU-gwYFQc'
TELEGRAM_CHAT_ID = '480055363'

# --- 3. INITIALIZATION ---
blynk = BlynkLib.Blynk(BLYNK_AUTH, server='blynk.cloud')
model = YOLO(MODEL_PATH)

system_armed = 1
tracker_timers = {}
alert_cooldown = 0
camera_error_sent = False

# --- 4. BACKGROUND TASKS ---
def send_telegram_summary(photo_path, final_count):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    try:
        with open(photo_path, 'rb') as photo:
            payload = {
                'chat_id': TELEGRAM_CHAT_ID,
                'caption': f"🚨 *SECURITY BREACH*\n👥 *Total People:* {final_count}\n⏰ {datetime.now().strftime('%I:%M:%S %p')}",
                'parse_mode': 'Markdown'
            }
            files = {'photo': photo}
            requests.post(url, data=payload, files=files, timeout=10)
    except Exception as e:
        print(f"Telegram Thread Error: {e}")

def send_telegram_emergency(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': f"⚠️ {message}", 'parse_mode': 'Markdown'}
        requests.post(url, data=payload, timeout=5)
    except: pass

@blynk.VIRTUAL_WRITE(0)
def v0_toggle_system(value):
    global system_armed
    system_armed = int(value[0])
    blynk.virtual_write(2, "SYSTEM ACTIVE" if system_armed else "SYSTEM STANDBY")

# --- 5. MAIN EXECUTION LOOP (YOUR PREFERRED STRUCTURE) ---
# Using index 2 as your default, but with a backup plan
cap = cv2.VideoCapture(2)
print("--- Smart Guard Degree Build: ONLINE ---")

while True:
    blynk.run()
    ret, frame = cap.read()

    # --- HEARTBEAT & FAIL-SAFE MONITORING ---
    if not ret:
        if not camera_error_sent:
            send_telegram_emergency("CAMERA OFFLINE: Hardware disconnected or stream lost.")
            blynk.virtual_write(3, "ERROR")
            camera_error_sent = True

        print("🚨 Camera Hardware Error! Attempting reconnect in 5s...")
        cap.release()  # Release the old handle properly
        cv2.destroyAllWindows()
        time.sleep(5)

        # Re-attempt to open the camera (Try 2, then try 0 as backup)
        cap = cv2.VideoCapture(2)
        if not cap.isOpened():
            cap = cv2.VideoCapture(2) # Backup index
            if not cap.isOpened():
                print("⏳ Still waiting for camera to be ready...")
                continue

        # Warm-up: Skip a few frames to clear the buffer
        for _ in range(5):
            cap.read()
        continue

    if camera_error_sent:
        blynk.virtual_write(3, "OK")
        camera_error_sent = False

    clean_frame = frame.copy()

    if system_armed:
        # Professional UI Header
        cv2.rectangle(frame, (0, 0), (frame.shape[1], 50), (0, 150, 0), -1)
        cv2.putText(frame, f"AI SURVEILLANCE - {datetime.now().strftime('%H:%M:%S')}", (20, 35), 1, 1.5, (255, 255, 255), 2)

        results = model.track(frame, persist=True, conf=0.5, verbose=False)
        current_frame_ids = []
        total_people_now = 0
        should_alert = False

        if results[0].boxes.id is not None:
            boxes = results[0].boxes.xyxy.cpu().numpy()
            ids = results[0].boxes.id.cpu().numpy().astype(int)
            clss = results[0].boxes.cls.cpu().numpy().astype(int)

            for box, id, cls in zip(boxes, ids, clss):
                if model.names[cls] == 'person':
                    total_people_now += 1
                    current_frame_ids.append(id)
                    x1, y1, x2, y2 = map(int, box)

                    # --- ANATOMICAL SEGMENTATION ---
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    h = y2 - y1
                    cv2.putText(frame, "HEAD", (x1, y1 + int(h * 0.1)), 1, 0.7, (0, 255, 255), 1)
                    cv2.putText(frame, "TORSO", (x1, y1 + int(h * 0.4)), 1, 0.7, (0, 255, 255), 1)
                    cv2.putText(frame, "LEGS", (x1, y1 + int(h * 0.8)), 1, 0.7, (0, 255, 255), 1)

                    if id not in tracker_timers:
                        tracker_timers[id] = time.time()

                    loiter_time = time.time() - tracker_timers[id]
                    countdown = 10 - int(loiter_time)

                    if countdown > 0:
                        cv2.putText(frame, f"DETECTING: {countdown}s", (x1, y1 - 15), 1, 1.2, (0, 255, 255), 2)
                    else:
                        should_alert = True
                        cv2.putText(frame, "ALERT TRIGGERED", (x1, y1 - 15), 1, 1.2, (0, 0, 255), 2)

        # Update Blynk Gauge
        blynk.virtual_write(1, total_people_now)

        if should_alert and time.time() > alert_cooldown:
            alert_cooldown = time.time() + 30
            # Using os.path.join for standalone reliability
            file_path = os.path.join(DATA_DIR, f"alert_{int(time.time())}.jpg")
            cv2.imwrite(file_path, clean_frame)
            threading.Thread(target=send_telegram_summary, args=(file_path, total_people_now)).start()

        for id in list(tracker_timers.keys()):
            if id not in current_frame_ids: del tracker_timers[id]
    else:
        cv2.rectangle(frame, (0, 0), (frame.shape[1], 50), (0, 0, 180), -1)
        cv2.putText(frame, "SYSTEM DISARMED / STANDBY", (20, 35), 1, 1.5, (255, 255, 255), 2)

    cv2.imshow("Smart Guard - Final Build", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'): break

cap.release()
cv2.destroyAllWindows()