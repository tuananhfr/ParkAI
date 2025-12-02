const InfoHeader = ({ stats }) => {
  if (!stats) {
    return null;
  }

  return (
    <div className="flex-grow-1 me-2">
      <div className="row g-1 text-center">
        <div className="col">
          <div
            className="fw-bold text-white"
            style={{
              fontSize: "1rem",
              lineHeight: "1.2",
            }}
          >
            {stats.entries_today || 0}
          </div>
          <div
            className="text-white-50"
            style={{ fontSize: "0.7rem", lineHeight: "1" }}
          >
            VÀO
          </div>
        </div>
        <div className="col position-relative">
          <div
            className="position-absolute start-0 top-0 bottom-0"
            style={{
              width: "1px",
              backgroundColor: "rgba(255, 255, 255, 0.25)",
            }}
          ></div>
          <div
            className="fw-bold text-white"
            style={{
              fontSize: "1rem",
              lineHeight: "1.2",
            }}
          >
            {stats.exits_today || 0}
          </div>
          <div
            className="text-white-50"
            style={{ fontSize: "0.7rem", lineHeight: "1" }}
          >
            RA
          </div>
        </div>
        <div className="col position-relative">
          <div
            className="position-absolute start-0 top-0 bottom-0"
            style={{
              width: "1px",
              backgroundColor: "rgba(255, 255, 255, 0.25)",
            }}
          ></div>
          <div
            className="fw-bold text-white"
            style={{
              fontSize: "1rem",
              lineHeight: "1.2",
            }}
          >
            {stats.vehicles_in_parking || 0}
          </div>
          <div
            className="text-white-50"
            style={{ fontSize: "0.7rem", lineHeight: "1" }}
          >
            Trong bãi
          </div>
        </div>
        <div className="col position-relative">
          <div
            className="position-absolute start-0 top-0 bottom-0"
            style={{
              width: "1px",
              backgroundColor: "rgba(255, 255, 255, 0.25)",
            }}
          ></div>
          <div
            className="fw-bold text-white"
            style={{
              fontSize: "1rem",
              lineHeight: "1.2",
            }}
          >
            {((stats.revenue_today || 0) / 1000).toFixed(0)}K
          </div>
          <div
            className="text-white-50"
            style={{ fontSize: "0.7rem", lineHeight: "1" }}
          >
            Thu
          </div>
        </div>
      </div>
    </div>
  );
};

export default InfoHeader;
