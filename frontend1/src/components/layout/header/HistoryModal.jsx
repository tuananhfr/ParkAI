import { CENTRAL_URL } from "@/config";
import HistoryPanel from "@/components/history/HistoryPanel";

/**
 * HistoryModal - Modal hiển thị lịch sử vào/ra
 */
const HistoryModal = ({ show, onClose, historyKey }) => {
  if (!show) return null;

  return (
    <div
      className="modal show d-block"
      style={{ backgroundColor: "rgba(0,0,0,0.5)" }}
      onClick={onClose}
    >
      <div
        className="modal-dialog modal-xl modal-dialog-scrollable"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-content">
          <div className="modal-header bg-primary text-white">
            <h5 className="modal-title">
              <i className="bi bi-clock-history me-2"></i>
              Lịch sử xe vào/ra
            </h5>
            <button
              type="button"
              className="btn-close btn-close-white"
              onClick={onClose}
            ></button>
          </div>
          <div className="modal-body p-0" style={{ height: "70vh" }}>
            <HistoryPanel key={historyKey} backendUrl={CENTRAL_URL} />
          </div>
        </div>
      </div>
    </div>
  );
};

export default HistoryModal;
