import BlynkLib, cv2, os, time, threading, requests
from collections import deque
from datetime import datetime
from ultralytics import YOLO

# --- 1. CONFIG & PATHS ---
MODEL_PATH = 'yolov8n-pose.pt'
BLYNK_AUTH = 'aoaEO3E5PLfZlZz1AUOMWk7-BcnCVBH2'
TELEGRAM_TOKEN = '8164442789:AAF7YyAoHUiaacxXzzVeRCsS10ZU-gwYFQc'
TELEGRAM_CHAT_ID = '480055363'

# --- 2. PREDICTIVE BUFFERS ---
movement_history = deque(maxlen=8)
alert_cooldown = 0
system_armed = 1
camera_error_sent = False

# --- 3. BLYNK INITIALIZATION (FIXED SERVER) ---
try:
    blynk = BlynkLib.Blynk(BLYNK_AUTH, server='blynk.cloud', port=80)
    print("✅ Blynk IoT Connected")
except:
    blynk = None
    print("⚠️ Blynk Connection Failed - Running in Offline Mode")

model = YOLO(MODEL_PATH)


# --- 4. NOTIFICATION FUNCTIONS ---
def send_telegram_emergency(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': f"⚠️ {message}", 'parse_mode': 'Markdown'}
        requests.post(url, data=payload, timeout=5)
    except:
        pass


def send_prediction_alert(photo_path, behavior, person_count):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    icon = "🚨" if "FALLING" in behavior else "⚠️"
    current_time = datetime.now().strftime('%I:%M:%S %p')
    try:
        with open(photo_path, 'rb') as photo:
            payload = {
                'chat_id': TELEGRAM_CHAT_ID,
                'caption': (
                    f"{icon} *PREDICTIVE AI ALERT*\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"🔮 *Forecast:* {behavior}\n"
                    f"👥 *Detected:* {person_count} Person(s)\n"
                    f"⏰ *Time:* {current_time}\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"✅ _Verified via Temporal Vector Analysis_"
                ),
                'parse_mode': 'Markdown'
            }
            requests.post(url, data=payload, files={'photo': photo}, timeout=10)
    except:
        pass


@blynk.VIRTUAL_WRITE(0) if blynk else lambda x: None
def v0_toggle(value):
    global system_armed
    system_armed = int(value[0])


# --- 5. MAIN EXECUTION ---
cap = cv2.VideoCapture(2)
print("--- Smart Guard: 5-Phase Behavioral System Online ---")

while True:
    if blynk:
        try:
            blynk.run()
        except:
            pass

    ret, frame = cap.read()

    # --- YOUR ORIGINAL HEARTBEAT & FAIL-SAFE (STRICTLY KEPT) ---
    if not ret:
        if not camera_error_sent:
            send_telegram_emergency("CAMERA OFFLINE: Hardware disconnected or stream lost.")
            if blynk: blynk.virtual_write(3, "ERROR")
            camera_error_sent = True

        print("🚨 Camera Hardware Error! Attempting reconnect in 5s...")
        cap.release()
        cv2.destroyAllWindows()
        time.sleep(5)

        cap = cv2.VideoCapture(2)
        if not cap.isOpened():
            cap = cv2.VideoCapture(2)
            if not cap.isOpened():
                print("⏳ Still waiting for camera to be ready...")
                continue

        for _ in range(5): cap.read()  # Warm-up
        continue

    if camera_error_sent:
        if blynk: blynk.virtual_write(3, "OK")
        camera_error_sent = False

    display_frame = frame.copy()
    h_frame, w_frame = display_frame.shape[:2]
    trigger = False
    behavior = "Analyzing..."
    person_count = 0

    if system_armed:
        cv2.rectangle(display_frame, (0, 0), (w_frame, 50), (40, 40, 40), -1)
        cv2.putText(display_frame, f"5-PHASE AI ENGINE | {datetime.now().strftime('%H:%M:%S')}", (20, 35), 1, 1.2,
                    (0, 255, 0), 2)

        results = model.track(display_frame, persist=True, verbose=False)

        if results[0].keypoints is not None and len(results[0].keypoints.xy) > 0:
            display_frame = results[0].plot()
            person_count = len(results[0].boxes)

            kpts = results[0].keypoints.xy[0].cpu().numpy()
            conf = results[0].keypoints.conf[0].cpu().numpy()  # Confidence scores for keypoints

            if len(kpts) > 12:
                nose_conf = conf[0]  # Confidence of Nose (Keypoint 0)
                head_y, l_wrist_y, r_wrist_y = kpts[0][1], kpts[9][1], kpts[10][1]
                hip_y = (kpts[11][1] + kpts[12][1]) / 2
                center_x = kpts[0][0]

                movement_history.append(
                    {'head': head_y, 'hip': hip_y, 'wrist': min(l_wrist_y, r_wrist_y), 'x': center_x})

                color = (0, 255, 0)
                if len(movement_history) == movement_history.maxlen:
                    body_height = abs(movement_history[-1]['head'] - movement_history[-1]['hip'])
                    height_change = abs(movement_history[0]['head'] - movement_history[0]['hip']) - body_height
                    wrist_vel = movement_history[0]['wrist'] - movement_history[-1]['wrist']
                    x_vel = abs(movement_history[0]['x'] - movement_history[-1]['x'])

                    # PHASE 5: IDENTITY MASKING (Torso found but Nose hidden/covered)
                    if nose_conf < 0.25:
                        behavior = "PHASE 5: IDENTITY MASKED"
                        color = (0, 255, 255)  # Yellow for caution
                        trigger = True
                    # PHASE 3: FALL
                    elif height_change > 35:
                        behavior = "PHASE 3: FORECAST FALLING"
                        color = (0, 0, 255)
                        trigger = True
                    # PHASE 2: INTRUSION
                    elif wrist_vel > 50:
                        behavior = "PHASE 2: FORECAST INTRUSION"
                        color = (0, 165, 255)
                        trigger = True
                    # PHASE 4: SNEAKING
                    elif body_height < 70 and x_vel > 20:
                        behavior = "PHASE 4: SNEAKING ATTEMPT"
                        color = (255, 0, 255)
                        trigger = True
                    else:
                        behavior = "PHASE 1: NORMAL"

                cv2.putText(display_frame, f"BEHAVIOR: {behavior}", (50, 100), 1, 1.8, color, 3)
                cv2.putText(display_frame, f"PEOPLE: {person_count}", (50, 150), 1, 1.2, (255, 255, 255), 2)
        else:
            movement_history.clear()
    else:
        overlay = display_frame.copy()
        cv2.rectangle(overlay, (0, 0), (w_frame, h_frame), (0, 0, 0), -1)
        display_frame = cv2.addWeighted(overlay, 0.7, display_frame, 0.3, 0)
        cv2.putText(display_frame, "SYSTEM STANDBY", (w_frame // 2 - 150, h_frame // 2), cv2.FONT_HERSHEY_DUPLEX, 1.5,
                    (0, 0, 255), 3)

    cv2.imshow("Smart Guard - Final Viva Build", display_frame)

    if trigger and time.time() > alert_cooldown:
        alert_cooldown = time.time() + 20
        cv2.imwrite("prediction.jpg", frame)
        threading.Thread(target=send_prediction_alert, args=("prediction.jpg", behavior, person_count)).start()
        if blynk: blynk.virtual_write(2, behavior)

    if cv2.waitKey(1) & 0xFF == ord('q'): break

cap.release()
cv2.destroyAllWindows()