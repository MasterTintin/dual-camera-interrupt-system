import cv2
import time
import os
import threading
import csv

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
    """ คลาสจัดการกล้องด้วย Multi-threading เพื่อความลื่นไหลระดับ Real-time """
    def __init__(self, src=0):
        self.capture = cv2.VideoCapture(src)
        self.ret, self.frame = self.capture.read()
        self.running = True
        self.lock = threading.Lock()
        
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

class SnapshotSaverThread:
    """ [ข้อ 3] แยก Thread สำหรับบันทึกภาพและคำนวณ Latency แบบไม่ให้หน้าจอหลักกระตุก """
    def __init__(self):
        self.queue = []
        self.running = True
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self.process_queue, args=(), daemon=True)
        self.thread.start()

    def add_task(self, frame0, frame1, irq_val, trigger_time):
        with self.lock:
            self.queue.append((frame0, frame1, irq_val, trigger_time))

    def process_queue(self):
        os.makedirs("captured_images", exist_ok=True)
        csv_file = "latency_log.csv"
        
        # สร้างไฟล์ CSV และเขียน Header หากยังไม่มี
        file_exists = os.path.exists(csv_file)
        with open(csv_file, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Timestamp", "IRQ_Count", "Latency_ms"])

        while self.running:
            task = None
            with self.lock:
                if self.queue:
                    task = self.queue.pop(0)
            
            if task:
                f0, f1, irq, start_t = task
                ts = int(start_t)

                if f0 is not None:
                    cv2.imwrite(f"captured_images/cam0_{ts}.jpg", f0)
                if f1 is not None:
                    cv2.imwrite(f"captured_images/cam1_{ts}.jpg", f1)
                
                end_t = time.time()
                latency = (end_t - start_t) * 1000 
                
                # บันทึกผลลง CSV
                with open(csv_file, mode="a", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow([ts, irq, f"{latency:.2f}"])
                
                print(f"💾 [Background Saver] บันทึกภาพคู่สำเร็จ! Latency: {latency:.2f} ms")
            else:
                time.sleep(0.01)

    def stop(self):
        self.running = False
        self.thread.join()

print("🚀 Starting Advanced Multi-Threaded Dual-Camera & Analytics System...")

# เปิดกล้องตัวหลักเดี่ยวๆ เพื่อป้องกันปัญหาแย่งพอร์ตบน Windows
cam0 = CameraStreamThread(0)
saver = SnapshotSaverThread()

print("✅ ระบบพร้อม! กด 'SPACEBAR' เพื่อ Trigger Interrupt / กด 'q' เพื่อออก")

flash_timer = 0

while True:
    ret0, frame0 = cam0.read()
    
    # ใช้เฟรมเดียวกันจำลองเป็น Dual-stream สำหรับทดสอบบน Windows เครื่องเดียว
    ret1, frame1 = ret0, frame0.copy() if ret0 and frame0 is not None else (False, None)

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
        flash_timer = start_t
        print(f"\n🚨 [SINGLE INTERRUPT TRIGGERED] at {start_t}")

        saver.add_task(frame0, frame1, current_irq, start_t)

    if key == ord('q'):
        break

cam0.release()
saver.stop()
cv2.destroyAllWindows()
print("System shutdown gracefully.")