/**
 * Component hiển thị thông tin xe (vào, ra, loại khách, giá vé)
 */
const VehicleInfo = ({ vehicleInfo, cameraType, isFullscreen }) => {
  return (
    <div className="mb-2">
      {/* Hàng 1: Vào + Loại khách */}
      <div className="d-flex justify-content-between align-items-center mb-1">
        <div className="text-muted" style={{ fontSize: "0.75rem" }}>
          {vehicleInfo.entry_time ? (
            <>
              <i
                className="bi bi-arrow-down-circle text-success me-1"
                style={{ fontSize: "0.7rem" }}
              ></i>
              Vào: {vehicleInfo.entry_time}
            </>
          ) : (
            <>
              <i
                className="bi bi-arrow-down-circle me-1"
                style={{ fontSize: "0.7rem", opacity: 0.5 }}
              ></i>
              Vào: Chưa có
            </>
          )}
        </div>
        <div className="d-flex align-items-center gap-1">
          <span className="text-muted" style={{ fontSize: "0.7rem" }}>
            <i className="bi bi-person-fill me-1"></i>Loại:
          </span>
          {vehicleInfo.is_subscriber ? (
            <span
              className="badge bg-success"
              style={{ fontSize: "0.7rem" }}
              title="Thuê bao - Miễn phí"
            >
              <i className="bi bi-star-fill me-1"></i>
              {vehicleInfo.customer_type === "company"
                ? "Công ty"
                : vehicleInfo.customer_type === "monthly"
                ? "Thẻ tháng"
                : "Thuê bao"}
            </span>
          ) : vehicleInfo.customer_type ? (
            <span className="badge bg-info" style={{ fontSize: "0.7rem" }}>
              {vehicleInfo.customer_type}
            </span>
          ) : (
            <span
              className="badge bg-secondary"
              style={{ fontSize: "0.7rem", opacity: 0.5 }}
            >
              Khách lẻ
            </span>
          )}
        </div>
      </div>

      {/* Hàng 2: Ra + Giá vé (chỉ ở cổng EXIT) */}
      {cameraType === "EXIT" && (
        <div className="d-flex justify-content-between align-items-center">
          <div className="text-muted" style={{ fontSize: "0.75rem" }}>
            {vehicleInfo.exit_time ? (
              <>
                <i
                  className="bi bi-arrow-up-circle text-danger me-1"
                  style={{ fontSize: "0.7rem" }}
                ></i>
                Ra: {vehicleInfo.exit_time}
              </>
            ) : (
              <>
                <i
                  className="bi bi-arrow-up-circle me-1"
                  style={{ fontSize: "0.7rem", opacity: 0.5 }}
                ></i>
                Ra: Chưa có
              </>
            )}
          </div>
          <div className="text-end">
            <div
              className={
                vehicleInfo.fee > 0 ? "fw-bold text-success" : "text-muted"
              }
              style={{ fontSize: "0.85rem" }}
            >
              {(vehicleInfo.fee || 0).toLocaleString("vi-VN")}
              <strong>đ</strong>
            </div>
            {vehicleInfo.duration && (
              <div className="text-muted" style={{ fontSize: "0.65rem" }}>
                <i className="bi bi-clock me-1"></i>
                {vehicleInfo.duration}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default VehicleInfo;

