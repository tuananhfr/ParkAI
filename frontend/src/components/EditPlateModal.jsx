import { useState } from "react";
import { validatePlateNumber } from "../utils/plateValidation";

/**
 * Modal để nhập biển số thủ công
 */
const EditPlateModal = ({
  show,
  initialPlateText,
  onClose,
  onConfirm,
  onNotification,
}) => {
  const [editPlateText, setEditPlateText] = useState(initialPlateText || "");

  const handleConfirm = () => {
    const normalizedPlate = editPlateText.trim().toUpperCase();

    if (!normalizedPlate || normalizedPlate.length < 5) {
      onNotification("⚠️ Biển số phải có ít nhất 5 ký tự!");
      return;
    }

    if (!validatePlateNumber(normalizedPlate)) {
      onNotification(
        "⚠️ Biển số không hợp lệ! Vui lòng nhập đúng định dạng (VD: 30A12345)"
      );
      return;
    }

    onConfirm(normalizedPlate);
    setEditPlateText("");
  };

  if (!show) return null;

  return (
    <div
      className="modal show d-block"
      style={{ backgroundColor: "rgba(0,0,0,0.5)" }}
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          onClose();
        }
      }}
    >
      <div
        className="modal-dialog modal-dialog-centered"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-content">
          <div className="modal-header bg-primary text-white">
            <h6 className="modal-title mb-0">
              <i className="bi bi-pencil-fill me-2"></i>
              Nhập biển số xe thủ công
            </h6>
            <button
              type="button"
              className="btn-close btn-close-white"
              onClick={onClose}
            ></button>
          </div>
          <div className="modal-body">
            <div className="mb-3">
              <label className="form-label">
                <i className="bi bi-123 me-1"></i>
                Biển số xe
              </label>
              <input
                type="text"
                className="form-control form-control-lg text-center fw-bold text-uppercase"
                value={editPlateText}
                onChange={(e) => setEditPlateText(e.target.value.toUpperCase())}
                placeholder="VD: 30A12345"
                style={{
                  fontSize: "1.2rem",
                  letterSpacing: "2px",
                }}
                onKeyPress={(e) => {
                  if (e.key === "Enter") {
                    handleConfirm();
                  }
                }}
                autoFocus
              />
              <small className="text-muted">
                Nhập biển số và nhấn Enter hoặc click "Xác nhận"
              </small>
            </div>
          </div>
          <div className="modal-footer">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={onClose}
            >
              Hủy
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleConfirm}
            >
              <i className="bi bi-check-circle-fill me-1"></i>
              Xác nhận
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default EditPlateModal;

