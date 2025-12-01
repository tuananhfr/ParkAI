"""
Fallback Handler - Xử lý khi xe không có trong cache (Central offline)
"""
import httpx
from typing import Tuple, Optional


class FallbackHandler:
    """
    Xử lý fallback khi xe không có trong cache

    Strategies:
    - ALLOW_FREE: Cho RA miễn phí
    - ALLOW_DEFAULT_FEE: Cho RA, tính phí mặc định
    - BLOCK: Chặn RA, yêu cầu admin
    - QUERY_BACKUP: Query Central khác
    """

    def __init__(self, config):
        self.config = config
        self.strategy = getattr(config, 'OFFLINE_EXIT_STRATEGY', 'ALLOW_DEFAULT_FEE')
        self.default_fee = getattr(config, 'DEFAULT_EXIT_FEE', 50000)
        self.backup_urls = getattr(config, 'BACKUP_CENTRAL_URLS', [])

    def handle_vehicle_not_found(
        self,
        plate_id: str,
        camera_type: str
    ) -> Tuple[bool, int, str]:
        """
        Xử lý khi xe KHÔNG CÓ trong cache

        Args:
            plate_id: Biển số xe (cleaned)
            camera_type: "ENTRY" or "EXIT"

        Returns:
            (allow: bool, fee: int, message: str)
        """

        if camera_type == "ENTRY":
            # Cổng VÀO: Không có trong cache là BÌNH THƯỜNG
            # Xe mới vào, chưa có record → OK
            return True, 0, "OK"

        elif camera_type == "EXIT":
            # Cổng RA: Không có trong cache → VẤN ĐỀ!
            # Có thể do:
            # 1. Xe chưa VÀO (gian lận)
            # 2. Central offline nên không sync được (hợp lệ)

            return self._handle_exit_not_found(plate_id)

        else:
            return False, 0, f"Invalid camera type: {camera_type}"

    def _handle_exit_not_found(self, plate_id: str) -> Tuple[bool, int, str]:
        """Handle EXIT khi không tìm thấy trong cache"""

        # STRATEGY 1: ALLOW_FREE - Cho RA miễn phí
        if self.strategy == "ALLOW_FREE":
            return (
                True,
                0,
                "⚠️ Offline mode: Xe không có record VÀO. Cho phép RA miễn phí."
            )

        # STRATEGY 2: ALLOW_DEFAULT_FEE - Cho RA, tính phí mặc định
        elif self.strategy == "ALLOW_DEFAULT_FEE":
            return (
                True,
                self.default_fee,
                f"⚠️ Offline mode: Tính phí mặc định {self.default_fee:,}đ"
            )

        # STRATEGY 3: BLOCK - Chặn RA, yêu cầu admin
        elif self.strategy == "BLOCK":
            return (
                False,
                0,
                "❌ Offline mode: Không tìm thấy record VÀO. Vui lòng liên hệ admin."
            )

        # STRATEGY 4: QUERY_BACKUP - Query Central khác
        elif self.strategy == "QUERY_BACKUP":
            result = self._query_backup_centrals(plate_id)

            if result:
                # Tìm thấy từ Central backup
                fee = result.get('fee', self.default_fee)
                entry_time = result.get('entry_time', 'N/A')
                entry_gate = result.get('entry_gate', 'N/A')

                return (
                    True,
                    fee,
                    f"✅ Tìm thấy từ Central backup. Gate {entry_gate}, VÀO lúc {entry_time}. Phí: {fee:,}đ"
                )
            else:
                # Không tìm thấy → Fallback: Cho RA miễn phí
                return (
                    True,
                    0,
                    "⚠️ Không tìm thấy record từ backup. Cho phép RA miễn phí."
                )

        else:
            # Unknown strategy → Default: BLOCK
            return (
                False,
                0,
                f"❌ Unknown strategy: {self.strategy}"
            )

    def _query_backup_centrals(self, plate_id: str) -> Optional[dict]:
        """
        Query Central servers khác để tìm vehicle record

        Returns:
            dict with vehicle info or None
        """
        if not self.backup_urls:
            return None

        print(f"🔍 Querying {len(self.backup_urls)} backup Centrals for {plate_id}...")

        for url in self.backup_urls:
            try:
                response = httpx.get(
                    f"{url}/api/vehicle/{plate_id}",
                    timeout=1.0
                )

                if response.status_code == 200:
                    data = response.json()

                    if data.get('success') and data.get('status') == 'IN':
                        print(f"✅ Found from backup: {url}")
                        return data

            except httpx.TimeoutException:
                print(f"⏱️  Timeout: {url}")
                continue
            except httpx.ConnectError:
                print(f"❌ Connect error: {url}")
                continue
            except Exception as e:
                print(f"❌ Error querying {url}: {e}")
                continue

        print(f"❌ Not found in any backup Central")
        return None

    def get_strategy_info(self) -> dict:
        """Get current strategy info"""
        return {
            "strategy": self.strategy,
            "default_fee": self.default_fee,
            "backup_centrals": len(self.backup_urls),
            "description": self._get_strategy_description()
        }

    def _get_strategy_description(self) -> str:
        """Get strategy description"""
        descriptions = {
            "ALLOW_FREE": "Cho phép RA miễn phí khi không tìm thấy record",
            "ALLOW_DEFAULT_FEE": f"Cho phép RA với phí mặc định {self.default_fee:,}đ",
            "BLOCK": "Chặn RA, yêu cầu liên hệ admin",
            "QUERY_BACKUP": "Query Central khác, fallback về FREE nếu không tìm thấy"
        }
        return descriptions.get(self.strategy, "Unknown")
