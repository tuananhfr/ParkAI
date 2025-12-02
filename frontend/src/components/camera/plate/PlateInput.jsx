/**
 * Input biển số xe với nút edit
 */
const PlateInput = ({ plateText, plateSource, onEditClick }) => {
  return (
    <div className="mb-2">
      <label className="form-label small mb-1 text-secondary">Biển số xe</label>
      <div className="input-group input-group-sm">
        <input
          type="text"
          value={plateText}
          readOnly
          className="form-control text-center fw-bold text-uppercase"
          placeholder="Chờ quét hoặc nhập tay..."
        />
        <button
          type="button"
          className="btn btn-outline-primary"
          onClick={onEditClick}
          title="Nhập biển số thủ công"
          style={{ fontSize: "0.75rem", padding: "0.25rem 0.5rem" }}
        >
          <i className="bi bi-pencil-fill"></i>
        </button>
      </div>
    </div>
  );
};

export default PlateInput;
