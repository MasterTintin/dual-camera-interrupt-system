import cv2
import time
import os
import threading

def get_usb_interrupt_count():
    try:
        with open("/proc/interrupts", "r") as f:
            lines = f.readlines()
            total_irq = 0
            for line in lines:
                if "xhci_hcd" in line or "usb" in line.lower():
                    parts = line.split()
                    for p in parts[1:]:
                        if p.isdigit():
                            total_irq += int(p)
            return total_irq
    except Exception as e:
        return "N/A (Non-Linux or Permission Error)"

print("Starting Real Hardware Dual-Camera & Linux IRQ Monitor...")

cap0 = cv2.VideoCapture(0)
cap1 = cv2.VideoCapture(2)

if not cap0.isOpened() or not cap1.isOpened():
    print("⚠️ Warning: เปิดกล้อง USB จริงไม่ครบ 2 ตัว เช็คพอร์ตหรือเลข Index (/dev/video*) อีกที!")

print("✅ ระบบพร้อม! กด 'SPACEBAR' เพื่อ Trigger Interrupt ถ่ายภาพ / กด 'q' เพื่อออก")

capture_flag = False

def keyboard_listener():
    global capture_flag

while True:
    ret0, frame0 = cap0.read()
    ret1, frame1 = cap1.read()

    current_irq = get_usb_interrupt_count()
    timestamp = time.time()

    if ret0:
        cv2.putText(frame0, f"Cam 0 | IRQ Count: {current_irq}", (20, 40), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.imshow("Real Hardware Cam 0", frame0)

    if ret1:
        cv2.putText(frame1, f"Cam 1 | IRQ Count: {current_irq}", (20, 40), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
        cv2.imshow("Real Hardware Cam 1", frame1)

    key = cv2.waitKey(1) & 0xFF
    if key == ord(' '):
        start_time = time.time()
        print(f"\n🚨 [SINGLE INTERRUPT TRIGGERED] at {start_time}")
        print(f"📊 USB Hardware IRQ Status from /proc/interrupts: {current_irq}")

        if ret0 and ret1:
            os.makedirs("captured_images", exist_ok=True)
            cv2.imwrite(f"captured_images/cam0_{int(start_time)}.jpg", frame0)
            cv2.imwrite(f"captured_images/cam1_{int(start_time)}.jpg", frame1)
            
            end_time = time.time()
            latency = (end_time - start_time) * 1000
            print(f"💾 บันทึกภาพสำเร็จ! Latency ทั้งกระบวนการ: {latency:.2f} ms")

    if key == ord('q'):
        break

cap0.release()
if cap1.isOpened():
    cap1.release()
cv2.destroyAllWindows()
print("System shutdown.")