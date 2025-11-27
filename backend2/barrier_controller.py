"""
Barrier Controller - Điều khiển thanh chắn (barrier)
"""
import time
import threading

class BarrierController:
    """Điều khiển barrier (thanh chắn)"""

    def __init__(self, enabled=False, gpio_pin=18, auto_close_time=5.0):
        self.enabled = enabled
        self.gpio_pin = gpio_pin
        self.auto_close_time = auto_close_time
        self.is_open = False

        if self.enabled:
            try:
                # TODO: Kết nối với GPIO để điều khiển motor
                # import RPi.GPIO as GPIO
                # GPIO.setmode(GPIO.BCM)
                # GPIO.setup(self.gpio_pin, GPIO.OUT)
                # GPIO.output(self.gpio_pin, GPIO.LOW)
                print(f"✅ Barrier controller initialized on GPIO pin {self.gpio_pin}")
            except Exception as e:
                print(f"❌ Failed to initialize GPIO: {e}")
                self.enabled = False
        else:
            print("⚠️  Barrier controller disabled (simulation mode)")

    def open_barrier(self):
        """Mở barrier"""
        if not self.enabled:
            print("🚪 [SIMULATION] Opening barrier...")
            self.is_open = True
            # Tự động đóng sau N giây
            threading.Timer(self.auto_close_time, self.close_barrier).start()
            return

        if self.is_open:
            print("⚠️  Barrier already open")
            return

        print("🚪 Opening barrier...")
        self.is_open = True

        # TODO: Kích hoạt relay/motor để mở
        # GPIO.output(self.gpio_pin, GPIO.HIGH)

        # Tự động đóng sau N giây
        threading.Timer(self.auto_close_time, self.close_barrier).start()

    def close_barrier(self):
        """Đóng barrier"""
        if not self.enabled:
            print("🚪 [SIMULATION] Closing barrier...")
            self.is_open = False
            return

        print("🚪 Closing barrier...")
        self.is_open = False

        # TODO: Kích hoạt relay/motor để đóng
        # GPIO.output(self.gpio_pin, GPIO.LOW)

    def get_status(self):
        """Lấy trạng thái barrier"""
        return {
            "is_open": self.is_open,
            "enabled": self.enabled
        }

    def cleanup(self):
        """Cleanup GPIO khi shutdown"""
        if self.enabled:
            try:
                # TODO: Cleanup GPIO
                # GPIO.cleanup()
                print("✅ Barrier GPIO cleaned up")
            except Exception as e:
                print(f"❌ Error cleaning up GPIO: {e}")
