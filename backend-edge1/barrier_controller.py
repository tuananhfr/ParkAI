"""
Barrier Controller - Điều khiển thanh chắn (barrier)
"""
import time
import threading

class BarrierController:
    """Điều khiển barrier (thanh chắn)"""

    def __init__(self, enabled=False, gpio_pin=18, auto_close_time=5.0, websocket_manager=None):
        self.enabled = enabled
        self.gpio_pin = gpio_pin
        self.auto_close_time = auto_close_time  # Giữ lại cho backward compatibility, nhưng không dùng nữa
        self.is_open = False
        self.close_timer = None  # Store timer để có thể cancel nếu cần
        self.websocket_manager = websocket_manager  # WebSocket để push status changes
        self.pending_entry = None  # Lưu tạm thông tin entry khi mở barrier (để lưu DB sau khi đóng)

        if self.enabled:
            try:
                # TODO: Kết nối với GPIO để điều khiển motor
                # import RPi.GPIO as GPIO
                # GPIO.setmode(GPIO.BCM)
                # GPIO.setup(self.gpio_pin, GPIO.OUT)
                # GPIO.output(self.gpio_pin, GPIO.LOW)
                pass
            except Exception as e:
                self.enabled = False
        else:
            pass

    def open_barrier(self, auto_close_delay=None, pending_entry=None):
        """
        Mở barrier
        
        Args:
            auto_close_delay: Số giây để tự động đóng (None = không tự động đóng)
                            - None: Barrier sẽ mở và chờ đóng thủ công hoặc barrier hồng ngoại
                            - Number: Tự động đóng sau N giây (cho backward compatibility)
            pending_entry: Thông tin entry tạm thời (plate_text, confidence, source, etc.) để lưu DB sau khi barrier đóng
        """
        # Lưu pending entry để lưu DB khi barrier đóng
        if pending_entry:
            self.pending_entry = pending_entry
        # Cancel timer đóng cửa nếu có
        if self.close_timer:
            self.close_timer.cancel()
            self.close_timer = None

        if not self.enabled:
            self.is_open = True
            self._broadcast_status()  # Push to frontend
            # Set auto close timer (simulation)
            if auto_close_delay:
                self._schedule_auto_close(auto_close_delay)
            return

        if self.is_open:
            return

        self.is_open = True

        # TODO: Kích hoạt relay/motor để mở
        # GPIO.output(self.gpio_pin, GPIO.HIGH)

        # Push status change to frontend
        self._broadcast_status()

        # Schedule auto close nếu có delay
        if auto_close_delay:
            self._schedule_auto_close(auto_close_delay)

    def _schedule_auto_close(self, delay):
        """Schedule tự động đóng barrier sau N giây"""
        def auto_close():
            time.sleep(delay)
            if self.is_open:  # Chỉ đóng nếu vẫn đang mở
                self.close_barrier()
        
        timer = threading.Thread(target=auto_close, daemon=True)
        timer.start()
        self.close_timer = timer

    def close_barrier(self):
        """
        Đóng barrier
        
        Returns:
            pending_entry: Thông tin entry tạm thời (nếu có) để lưu DB sau khi đóng
        """
        # Cancel timer đóng cửa nếu có
        if self.close_timer:
            self.close_timer.cancel()
            self.close_timer = None

        # Lấy pending entry trước khi reset
        pending_entry = self.pending_entry
        self.pending_entry = None

        if not self.enabled:
            self.is_open = False
            self._broadcast_status()  # Push to frontend
            return pending_entry

        self.is_open = False

        # TODO: Kích hoạt relay/motor để đóng
        # GPIO.output(self.gpio_pin, GPIO.LOW)

        # Push status change to frontend
        self._broadcast_status()
        
        return pending_entry

    def get_status(self):
        """Lấy trạng thái barrier"""
        return {
            "is_open": self.is_open,
            "enabled": self.enabled
        }

    def _broadcast_status(self):
        """Broadcast barrier status change qua WebSocket"""
        if self.websocket_manager:
            status = self.get_status()
            self.websocket_manager.broadcast_barrier_status(status)

    def cleanup(self):
        """Cleanup GPIO khi shutdown"""
        if self.enabled:
            try:
                # TODO: Cleanup GPIO
                # GPIO.cleanup()
                pass
            except Exception as e:
                pass
