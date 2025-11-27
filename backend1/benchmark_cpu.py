#!/usr/bin/env python3
"""
CPU & Memory Benchmark - IMX500 Optimization
"""
import time
import psutil
import os
import config
from camera_manager import CameraManager
from detection_service import DetectionService
from websocket_manager import WebSocketManager

def get_process_stats():
    """Lấy CPU và RAM usage của process hiện tại"""
    process = psutil.Process(os.getpid())
    cpu_percent = process.cpu_percent(interval=1.0)
    mem_info = process.memory_info()
    mem_mb = mem_info.rss / 1024 / 1024
    return cpu_percent, mem_mb

print("=" * 60)
print("📊 IMX500 PERFORMANCE BENCHMARK")
print("=" * 60)
print(f"Resolution: {config.RESOLUTION_WIDTH}x{config.RESOLUTION_HEIGHT}")
print(f"Camera FPS: {config.CAMERA_FPS}")
print(f"Detection FPS: {config.DETECTION_FPS}")
print(f"Queue size: {config.MAX_FRAME_QUEUE_SIZE}")
print("=" * 60)

# Initialize
print("\n1️⃣ Initializing camera...")
camera_manager = CameraManager(config.MODEL_PATH, config.LABELS_PATH)
camera_manager.start()
time.sleep(2)

cpu, mem = get_process_stats()
print(f"   CPU: {cpu:.1f}% | RAM: {mem:.1f}MB")

print("\n2️⃣ Initializing detection service...")
websocket_manager = WebSocketManager()
detection_service = DetectionService(camera_manager, websocket_manager, None)
detection_service.start()
time.sleep(2)

cpu, mem = get_process_stats()
print(f"   CPU: {cpu:.1f}% | RAM: {mem:.1f}MB")

print("\n3️⃣ Running benchmark for 30 seconds...")
print("=" * 60)

samples = []
start_time = time.time()

try:
    for i in range(30):
        time.sleep(1)
        cpu, mem = get_process_stats()
        samples.append((cpu, mem))

        elapsed = i + 1
        avg_cpu = sum(s[0] for s in samples) / len(samples)
        avg_mem = sum(s[1] for s in samples) / len(samples)

        print(f"[{elapsed:2d}s] CPU: {cpu:5.1f}% (avg: {avg_cpu:5.1f}%) | "
              f"RAM: {mem:6.1f}MB (avg: {avg_mem:6.1f}MB) | "
              f"Detections: {detection_service.total_detections} | "
              f"FPS: {detection_service.fps}")

except KeyboardInterrupt:
    print("\n\n⏹️  Stopped by user")

# Calculate stats
print("\n" + "=" * 60)
print("📊 BENCHMARK RESULTS")
print("=" * 60)

if samples:
    cpus = [s[0] for s in samples]
    mems = [s[1] for s in samples]

    print(f"CPU Usage:")
    print(f"  Min:     {min(cpus):.1f}%")
    print(f"  Max:     {max(cpus):.1f}%")
    print(f"  Average: {sum(cpus)/len(cpus):.1f}%")
    print()
    print(f"Memory Usage:")
    print(f"  Min:     {min(mems):.1f}MB")
    print(f"  Max:     {max(mems):.1f}MB")
    print(f"  Average: {sum(mems)/len(mems):.1f}MB")
    print()
    print(f"Detection Stats:")
    print(f"  Total detections: {detection_service.total_detections}")
    print(f"  Total frames: {detection_service.total_frames}")
    print(f"  Detection FPS: {detection_service.fps}")
    print()

    # Performance grade
    avg_cpu = sum(cpus) / len(cpus)
    if avg_cpu < 20:
        grade = "🏆 EXCELLENT (IMX500 tối ưu)"
    elif avg_cpu < 30:
        grade = "✅ GOOD"
    elif avg_cpu < 40:
        grade = "⚠️  ACCEPTABLE"
    else:
        grade = "❌ HIGH (cần tối ưu thêm)"

    print(f"Performance Grade: {grade}")

print("=" * 60)

# Cleanup
detection_service.stop()
camera_manager.stop()

print("✅ Benchmark complete")
