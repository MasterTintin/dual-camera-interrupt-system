import csv
import matplotlib.pyplot as plt
import os

csv_file = "latency_log.csv"

timestamps = []
irq_counts = []
latencies = []

if not os.path.exists(csv_file):
    print(f"❌ ไม่พบไฟล์ {csv_file}! กรุณารัน main.py และกด Spacebar เพื่อเก็บข้อมูลก่อนนะเพื่อน")
    exit()

with open(csv_file, mode="r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        timestamps.append(float(row["Timestamp"]))
        irq_counts.append(int(row["IRQ_Count"]))
        latencies.append(float(row["Latency_ms"]))

if not latencies:
    print("⚠️ ยังไม่มีข้อมูล Latency!")
    exit()

mean_latency = sum(latencies) / len(latencies)
max_latency = max(latencies)
min_latency = min(latencies)

print(f"📊 สถิติ Latency:")
print(f" - ค่าเฉลี่ย (Mean Latency): {mean_latency:.2f} ms")
print(f" - ค่าสูงสุด (Max Latency): {max_latency:.2f} ms")
print(f" - ค่าต่ำสุด (Min Latency): {min_latency:.2f} ms")

# สร้างรูปกราฟ 2 ช่องในรูปเดียว
plt.style.use('seaborn-v0_8-darkgrid' if 'seaborn-v0_8-darkgrid' in plt.style.available else 'default')
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))

# กราฟที่ 1: Latency Trend (แนวโน้มความหน่วงตามแต่ละ Trigger)
ax1.plot(latencies, marker='o', color='b', linestyle='-', linewidth=2, markersize=6)
ax1.set_title("Dual-Camera Interrupt Trigger Latency Analysis", fontsize=14, fontweight='bold')
ax1.set_ylabel("Latency (ms)", fontsize=12)
ax1.set_ylim(0, max(latencies) * 1.2 if max(latencies) > 0 else 10)
ax1.grid(True)

# กราฟที่ 2: Latency Distribution (การกระจายตัวของความหน่วง)
ax2.hist(latencies, bins=min(5, len(latencies)), color='orange', edgecolor='black', alpha=0.7)
ax2.set_title("Latency Distribution & Jitter Analysis", fontsize=12, fontweight='bold')
ax2.set_xlabel("Latency (ms)", fontsize=12)
ax2.set_ylabel("Frequency", fontsize=12)
ax2.grid(True)

plt.tight_layout()

# บันทึกรูปกราฟ
output_img = "latency_analysis_report.png"
plt.savefig(output_img, dpi=300)
print(f"💾 บันทึกกราฟสถิติเรียบร้อยแล้วที่ไฟล์: {output_img}")

# แสดงกราฟ
plt.show()