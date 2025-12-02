/**
 * Component hiển thị ảnh biển số đã phát hiện
 */
const PlateImage = ({ plateImage }) => {
  return (
    <div className="mb-2 text-center">
      <label className="form-label small mb-1 text-secondary d-block">
        <i className="bi bi-image-fill me-1"></i>
        Ảnh biển số đã phát hiện
      </label>
      <div
        className="d-inline-block p-1 bg-white border border-2 rounded"
        style={{
          maxWidth: "100%",
          minHeight: "60px",
          minWidth: "150px",
          borderColor: plateImage ? "#0d6efd" : "#dee2e6",
          transition: "border-color 0.3s ease",
        }}
      >
        {plateImage ? (
          <img
            src={plateImage}
            alt="Cropped plate"
            style={{
              maxWidth: "100%",
              height: "auto",
              maxHeight: "80px",
              display: "block",
              imageRendering: "crisp-edges",
            }}
          />
        ) : (
          <div
            className="d-flex align-items-center justify-content-center text-muted"
            style={{ minHeight: "60px" }}
          >
            <div className="text-center">
              <i className="bi bi-image fs-4 opacity-25"></i>
              <div className="small mt-1" style={{ fontSize: "0.7rem" }}>
                Chờ phát hiện...
              </div>
            </div>
          </div>
        )}
      </div>
      {plateImage && (
        <small
          className="text-muted d-block mt-0"
          style={{ fontSize: "0.65rem" }}
        >
          Vùng ảnh được OCR phân tích
        </small>
      )}
    </div>
  );
};

export default PlateImage;
