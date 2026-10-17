import sys
import cv2
import time
import os
import threading
import csv
import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel, 
                             QPushButton, QVBoxLayout, QHBoxLayout)

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
    """ คลาสจัดการกล้องด้วย Multi-threading """
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
    """ แยก Thread สำหรับบันทึกภาพและบันทึก CSV แบบไม่ให้ GUI กระตุก """
    def __init__(self, callback_on_complete=None):
        self.queue = []
        self.running = True
        self.lock = threading.Lock()
        self.callback = callback_on_complete
        self.thread = threading.Thread(target=self.process_queue, args=(), daemon=True)
        self.thread.start()

    def add_task(self, frame0, frame1, irq_val, trigger_time):
        with self.lock:
            self.queue.append((frame0, frame1, irq_val, trigger_time))

    def process_queue(self):
        os.makedirs("captured_images", exist_ok=True)
        csv_file = "latency_log.csv"
        
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
                
                with open(csv_file, mode="a", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow([ts, irq, f"{latency:.2f}"])
                
                print(f"💾 [Background Saver] บันทึกสำเร็จ! Latency: {latency:.2f} ms")
                if self.callback:
                    self.callback(latency)
            else:
                time.sleep(0.01)

    def stop(self):
        self.running = False
        self.thread.join()

class MplCanvas(FigureCanvas):
    """ Canvas สำหรับวาดกราฟ Matplotlib ใน PyQt """
    def __init__(self, parent=None, width=5, height=3, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111)
        super(MplCanvas, self).__init__(fig)

class DualCameraDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dual-Camera Interrupt & Analytics Dashboard")
        self.setGeometry(50, 50, 1150, 680)

        self.cam0 = CameraStreamThread(0)
        self.saver = SnapshotSaverThread(callback_on_complete=self.on_save_completed)

        self.latencies = []
        self.flash_timer = 0

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        left_layout = QVBoxLayout()
        
        self.label_cam0 = QLabel("Cam 0 Stream")
        self.label_cam0.setAlignment(Qt.AlignCenter)
        self.label_cam0.setStyleSheet("background-color: black; color: white; border: 2px solid #0000ff; font-weight: bold;")
        self.label_cam0.setFixedSize(480, 270)
        
        self.label_cam1 = QLabel("Cam 1 Stream")
        self.label_cam1.setAlignment(Qt.AlignCenter)
        self.label_cam1.setStyleSheet("background-color: black; color: white; border: 2px solid #ff0000; font-weight: bold;")
        self.label_cam1.setFixedSize(480, 270)

        left_layout.addWidget(self.label_cam0)
        left_layout.addWidget(self.label_cam1)


        right_layout = QVBoxLayout()
        
        self.title_label = QLabel("📊 System Control & Real-time Analytics")
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50;")
        
        self.status_label = QLabel("Status: System Ready\nIRQ Count: 1000 | Last Latency: N/A")
        self.status_label.setStyleSheet("font-size: 13px; color: #27ae60; background-color: #e8f8f5; padding: 10px; border-radius: 5px;")
        
        self.trigger_button = QPushButton("🚨 Trigger Interrupt Snapshot (SPACEBAR)")
        self.trigger_button.setStyleSheet("font-size: 14px; padding: 12px; background-color: #ff4757; color: white; font-weight: bold; border-radius: 5px;")
        self.trigger_button.clicked.connect(self.trigger_interrupt)

        self.canvas = MplCanvas(self, width=5, height=3, dpi=80)
        self.canvas.axes.set_title("Real-time Latency (ms)", fontsize=10)
        self.canvas.axes.set_ylabel("ms")
        self.canvas.axes.grid(True)

        right_layout.addWidget(self.title_label)
        right_layout.addWidget(self.status_label)
        right_layout.addWidget(self.trigger_button)
        right_layout.addWidget(self.canvas)

        main_layout.addLayout(left_layout)
        main_layout.addLayout(right_layout)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frames)
        self.timer.start(30)

    def keyPressEvent(self, event):
        """ กด Spacebar บนคีย์บอร์ดเพื่อสั่ง Trigger ได้เหมือนเดิม """
        if event.key() == Qt.Key_Space:
            self.trigger_interrupt()
        else:
            super().keyPressEvent(event)

    def trigger_interrupt(self):
        start_t = time.time()
        self.flash_timer = start_t
        current_irq = get_usb_interrupt_count()
        
        ret0, frame0 = self.cam0.read()
        ret1, frame1 = ret0, frame0.copy() if ret0 and frame0 is not None else (False, None)

        self.saver.add_task(frame0, frame1, current_irq, start_t)
        self.status_label.setText(f"🚨 Status: INTERRUPT FIRED!\nIRQ Count: {current_irq} | Processing Snapshot...")

    def on_save_completed(self, latency):
        self.latencies.append(latency)
        current_irq = get_usb_interrupt_count()
        
        self.status_label.setText(f"✅ Status: Snapshot Saved!\nIRQ Count: {current_irq} | Latency: {latency:.2f} ms")
        
        self.canvas.axes.cla()
        self.canvas.axes.plot(self.latencies, marker='o', color='b', linestyle='-')
        self.canvas.axes.set_title("Real-time Latency Trend (ms)", fontsize=10)
        self.canvas.axes.set_ylabel("Latency (ms)")
        self.canvas.axes.grid(True)
        self.canvas.draw()

    def update_frames(self):
        ret0, frame0 = self.cam0.read()
        ret1, frame1 = ret0, frame0.copy() if ret0 and frame0 is not None else (False, None)

        current_irq = get_usb_interrupt_count()
        is_flashing = (time.time() - self.flash_timer) < 0.3

        if ret0 and frame0 is not None:
            if is_flashing:
                cv2.rectangle(frame0, (0, 0), (frame0.shape[1], frame0.shape[0]), (0, 0, 255), 10)
            cv2.putText(frame0, f"Cam 0 | IRQ: {current_irq}", (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            
            rgb = cv2.cvtColor(frame0, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            qt_img = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
            self.label_cam0.setPixmap(QPixmap.fromImage(qt_img).scaled(self.label_cam0.size(), Qt.KeepAspectRatio))

        if ret1 and frame1 is not None:
            if is_flashing:
                cv2.rectangle(frame1, (0, 0), (frame1.shape[1], frame1.shape[0]), (0, 0, 255), 10)
            cv2.putText(frame1, f"Cam 1 | IRQ: {current_irq}", (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
            
            rgb = cv2.cvtColor(frame1, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            qt_img = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
            self.label_cam1.setPixmap(QPixmap.fromImage(qt_img).scaled(self.label_cam1.size(), Qt.KeepAspectRatio))

    def closeEvent(self, event):
        self.cam0.release()
        self.saver.stop()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    dashboard = DualCameraDashboard()
    dashboard.show()
    sys.exit(app.exec_())