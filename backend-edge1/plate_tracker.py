"""
Plate Tracker - Track và vote cho biển số chính xác nhất
"""
import time
from collections import defaultdict
from difflib import SequenceMatcher
import config


class PlateTracker:
    """
    Track OCR results qua nhiều frames và vote cho kết quả tốt nhất

    Logic:
    1. Thu thập OCR results trong N giây
    2. Group các plates giống nhau (similarity > 80%)
    3. Chọn plate xuất hiện nhiều nhất
    4. Chỉ accept nếu xuất hiện >= min_votes lần
    """

    def __init__(self, window_seconds=3, min_votes=3, similarity_threshold=0.8):
        """
        Args:
            window_seconds: Thời gian thu thập votes (giây)
            min_votes: Số votes tối thiểu để accept
            similarity_threshold: Ngưỡng similarity để group plates
        """
        self.window_seconds = window_seconds
        self.min_votes = min_votes
        self.similarity_threshold = similarity_threshold

        # Track plates theo detection box
        self.trackers = {}  # {bbox_key: PlateVotes}

    def add_detection(self, bbox, plate_text):
        """
        Add OCR result cho 1 detection box

        Args:
            bbox: (x, y, w, h) - detection box
            plate_text: OCR result

        Returns:
            None hoặc final_plate nếu đã đủ votes
        """
        bbox_key = self._get_bbox_key(bbox)

        # Create tracker cho box nay neu chua co
        if bbox_key not in self.trackers:
            self.trackers[bbox_key] = PlateVotes(
                window_seconds=self.window_seconds,
                min_votes=self.min_votes,
                similarity_threshold=self.similarity_threshold
            )

        tracker = self.trackers[bbox_key]
        result = tracker.add_vote(plate_text)

        # Cleanup old trackers
        self._cleanup_old_trackers()

        return result

    def _get_bbox_key(self, bbox):
        """Convert bbox to hashable key với tolerance"""
        x, y, w, h = bbox
        # Round to 10px tolerance
        return (round(x / 10) * 10, round(y / 10) * 10, round(w / 10) * 10, round(h / 10) * 10)

    def _cleanup_old_trackers(self):
        """Xóa trackers cũ hơn window_seconds * 2"""
        current_time = time.time()
        timeout = self.window_seconds * 2

        keys_to_remove = []
        for key, tracker in self.trackers.items():
            if current_time - tracker.first_seen > timeout:
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del self.trackers[key]


class PlateVotes:
    """Vote counter cho 1 plate detection"""

    def __init__(self, window_seconds=3, min_votes=3, similarity_threshold=0.8):
        self.window_seconds = window_seconds
        self.min_votes = min_votes
        self.similarity_threshold = similarity_threshold

        self.votes = []  # [(plate_text, timestamp), ...]
        self.first_seen = time.time()
        self.finalized = False
        self.final_result = None

    def add_vote(self, plate_text):
        """
        Add vote cho plate text với EARLY STOP

        Returns:
            None nếu chưa đủ votes, hoặc final_plate nếu đã consensus
        """
        # Neu da finalized, return ket qua
        if self.finalized:
            return self.final_result

        # Add vote
        current_time = time.time()
        self.votes.append((plate_text, current_time))

        # Remove votes ngoai window
        cutoff_time = current_time - self.window_seconds
        self.votes = [(text, ts) for text, ts in self.votes if ts >= cutoff_time]

        # EARLY STOP: Check ngay neu co du votes giong nhau
        early_stop_enabled = getattr(config, 'EARLY_STOP_ENABLED', True)

        if early_stop_enabled:
            result = self._check_early_stop()
            if result:
                self.finalized = True
                self.final_result = result
                print(f"⚡ EARLY STOP: {result} ({len(self.votes)} votes in {current_time - self.first_seen:.2f}s)")
                return result

        # Fallback: Check neu du votes (old logic)
        if len(self.votes) >= self.min_votes:
            result = self._get_consensus()
            if result:
                self.finalized = True
                self.final_result = result
                return result

        return None

    def _check_early_stop(self):
        """
        Check early stop: Nếu có >= min_votes votes GIỐNG NHAU → Stop ngay

        Returns:
            plate_text nếu đủ votes giống nhau, hoặc None
        """
        from collections import Counter

        if len(self.votes) < self.min_votes:
            return None

        # Count votes sau khi normalize (bo ky tu dac biet)
        normalized_votes = []
        vote_mapping = {}  # {normalized: [original, ...]}

        for plate_text, _ in self.votes:
            # Normalize: CHI GIU SO + CHU
            normalized = ''.join(c.upper() for c in plate_text if c.isalnum())
            normalized_votes.append(normalized)

            if normalized not in vote_mapping:
                vote_mapping[normalized] = []
            vote_mapping[normalized].append(plate_text)

        # Dem votes
        vote_counts = Counter(normalized_votes)
        most_common_normalized, count = vote_counts.most_common(1)[0]

        # Neu du min_votes → STOP NGAY!
        if count >= self.min_votes:
            # Chon ban dep nhat tu cac original votes
            original_votes = vote_mapping[most_common_normalized]
            return self._select_best_format(original_votes)

        return None

    def _get_consensus(self):
        """
        Tìm consensus từ votes

        Returns:
            plate_text có votes cao nhất, hoặc None
        """
        if not self.votes:
            return None

        # Group similar plates
        groups = self._group_similar_plates()

        # Find group voi votes nhieu nhat
        best_group = max(groups, key=lambda g: len(g['votes']))

        # Check neu dat min_votes
        if len(best_group['votes']) >= self.min_votes:
            # Chon plate CO FORMAT DEP NHAT trong group
            return self._select_best_format(best_group['votes'])

        return None

    def _group_similar_plates(self):
        """
        Group các plates giống nhau (similarity > threshold)

        Returns:
            [{'representative': str, 'votes': [str, ...]}, ...]
        """
        groups = []

        for plate_text, _ in self.votes:
            # Tim group phu hop
            added = False
            for group in groups:
                if self._is_similar(plate_text, group['representative']):
                    group['votes'].append(plate_text)
                    added = True
                    break

            # Tao group moi neu khong match
            if not added:
                groups.append({
                    'representative': plate_text,
                    'votes': [plate_text]
                })

        return groups

    def _select_best_format(self, votes):
        """
        Chọn plate theo logic ĐƠN GIẢN:
        1. Lấy bản NHIỀU VOTES NHẤT
        2. Nếu bản đó KHÔNG CÓ dấu → tìm version khác CÓ dấu (cùng số + chữ)
        3. Nếu không tìm thấy → trả về bản NHIỀU VOTES (không format)

        KHÔNG TỰ ĐỘNG FORMAT!

        Returns:
            plate_text từ OCR (không tự format)
        """
        from collections import Counter

        # Dem votes
        vote_counts = Counter(votes)
        most_common_plate = vote_counts.most_common(1)[0][0]

        # Neu da co dau - hoac . → tra ve luon
        if '-' in most_common_plate or '.' in most_common_plate:
            return most_common_plate

        # Neu chua co dau → TIM version khac CO dau (cung so + chu)
        best_with_format = self._find_formatted_version(most_common_plate, votes)

        if best_with_format:
            return best_with_format

        # Khong tim thay → tra ve ban NHIEU VOTES (khong format)
        return most_common_plate

    def _find_formatted_version(self, base_plate, votes):
        """
        Tìm version có dấu - hoặc . (cùng số + chữ với base_plate)

        Ưu tiên:
        1. Có cả - và .
        2. Chỉ có -
        3. Chỉ có .

        Returns:
            plate_text hoặc None
        """
        # Normalize base
        base_normalized = ''.join(c.upper() for c in base_plate if c.isalnum())

        # Tim cac version co dau
        with_both = []      # Co ca - va .
        with_dash = []      # Chi co -
        with_dot = []       # Chi co .

        for vote in votes:
            vote_normalized = ''.join(c.upper() for c in vote if c.isalnum())

            # Cung so + chu?
            if vote_normalized == base_normalized:
                has_dash = '-' in vote
                has_dot = '.' in vote

                if has_dash and has_dot:
                    with_both.append(vote)
                elif has_dash:
                    with_dash.append(vote)
                elif has_dot:
                    with_dot.append(vote)

        # Uu tien: co ca 2 > chi dash > chi dot
        if with_both:
            return with_both[0]
        elif with_dash:
            return with_dash[0]
        elif with_dot:
            return with_dot[0]

        return None

    def _is_similar(self, text1, text2):
        """
        Check nếu 2 plates giống nhau

        CHỈ SO SÁNH SỐ + CHỮ (bỏ hết ký tự đặc biệt)
        Ví dụ: "29A-179.90" == "29A17990" == "29A-17990"
        """
        # Normalize: CHI GIU SO VA CHU
        t1 = ''.join(c.upper() for c in text1 if c.isalnum())
        t2 = ''.join(c.upper() for c in text2 if c.isalnum())

        # Exact match sau khi normalize
        if t1 == t2:
            return True

        # Similarity ratio (cho phep sai lech nho)
        ratio = SequenceMatcher(None, t1, t2).ratio()
        return ratio >= self.similarity_threshold


# Global instance
_plate_tracker = None


def get_plate_tracker():
    """Get singleton instance"""
    global _plate_tracker
    if _plate_tracker is None:
        _plate_tracker = PlateTracker(
            window_seconds=getattr(config, 'PLATE_VOTE_WINDOW', 1.5),      # Thu thập votes trong N giây (mặc định 1.5s)
            min_votes=getattr(config, 'PLATE_MIN_VOTES', 2),               # Cần ít nhất N votes (mặc định 2)
            similarity_threshold=getattr(config, 'PLATE_SIMILARITY_THRESHOLD', 0.85)  # 85% giống nhau
        )
    return _plate_tracker
