import cv2
import time
import os
import threading
\
_mock_irq_counter = 1000

def get_usb_interrupt_count():
    """ อ่านค่า /proc/interrupts บน Linux หรือใช้ Mock Counter บน Windows """
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
    except Exception:
        global _mock_irq_counter
        _mock_irq_counter += 15
        return _mock_irq_counter

class CameraStreamThread:
    """ คลาสสำหรับจัดการกล้องแต่ละตัวด้วย Multi-threading เพื่อความลื่นไหลระดับ Real-time """
    def __init__(self, src=0):
        self.capture = cv2.VideoCapture(src)
        self.ret, self.frame = self.capture.read()
        self.running = True
        self.lock = threading.Lock()
        
        # เริ่ม Background Thread อ่านเฟรมภาพ
        self.thread = threading.Thread(target=self.update, args=(), daemon=True)
        self.thread.start()

    def update(self):
        while self.running:
            ret, frame = self.capture.read()
            with self.lock:
                self.ret = ret
                self.frame = frame
            time.sleep(0.01)

    def read(self):
        with self.lock:
            return self.ret, self.frame.copy() if self.ret else (False, None)

    def release(self):
        self.running = False
        self.thread.join()
        self.capture.release()

print("🚀 Starting Multi-Threaded Dual-Camera & IRQ Monitor System...")

cam0_src = 0
cam1_src = 0 

cam0 = CameraStreamThread(cam0_src)
cam1 = CameraStreamThread(cam1_src)

print("✅ ระบบพร้อม! กด 'SPACEBAR' เพื่อ Trigger Interrupt ถ่ายภาพ / กด 'q' เพื่อออก")

flash_timer = 0 

while True:
    ret0, frame0 = cam0.read()
    ret1, frame1 = cam1.read()

    current_irq = get_usb_interrupt_count()
    current_time = time.time()

    is_flashing = (current_time - flash_timer) < 0.3

    if ret0 and frame0 is not None:
        if is_flashing:
            cv2.rectangle(frame0, (0, 0), (frame0.shape[1], frame0.shape[0]), (0, 0, 255), 10)
            cv2.putText(frame0, "!!! INTERRUPT FIRED !!!", (40, 90), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 3)
        
        cv2.putText(frame0, f"Cam 0 | IRQ Count: {current_irq}", (20, 40), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.imshow("Multi-Threaded Cam 0", frame0)

    if ret1 and frame1 is not None:
        if is_flashing:
            cv2.rectangle(frame1, (0, 0), (frame1.shape[1], frame1.shape[0]), (0, 0, 255), 10)
            cv2.putText(frame1, "!!! INTERRUPT FIRED !!!", (40, 90), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 3)

        cv2.putText(frame1, f"Cam 1 | IRQ Count: {current_irq}", (20, 40), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
        cv2.imshow("Multi-Threaded Cam 1", frame1)

    key = cv2.waitKey(1) & 0xFF
    
    if key == ord(' '):
        start_t = time.time()
        flash_timer = start_t  # สั่งเปิด Visual Effect แวบแดง
        print(f"\n🚨 [SINGLE INTERRUPT TRIGGERED] at {start_t}")
        print(f"📊 USB Hardware IRQ Status: {current_irq}")

        if ret0 and ret1:
            os.makedirs("captured_images", exist_ok=True)
            cv2.imwrite(f"captured_images/cam0_{int(start_t)}.jpg", frame0)
            cv2.imwrite(f"captured_images/cam1_{int(start_t)}.jpg", frame1)
            
            end_t = time.time()
            latency = (end_t - start_t) * 1000
            print(f"💾 บันทึกภาพคู่สำเร็จ! Latency: {latency:.2f} ms")

    if key == ord('q'):
        break

cam0.release()
cam1.release()
cv2.destroyAllWindows()
print("System shutdown gracefully.")