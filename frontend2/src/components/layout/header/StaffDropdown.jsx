import { useState } from "react";
import DynamicButton from "@/components/button/DynamicButton";
/**
 * StaffDropdown - Component dropdown quản lý người trực
 */
const StaffDropdown = ({ staff, onFetchStaff, onToggleStatus, onSave }) => {
  const [showDropdown, setShowDropdown] = useState(false);

  const handleToggle = () => {
    const newState = !showDropdown;
    setShowDropdown(newState);
    if (newState && onFetchStaff) {
      onFetchStaff();
    }
  };

  return (
    <div className="position-relative">
      <DynamicButton
        icon="bi-people-fill"
        text="Người trực"
        onClick={handleToggle}
        size="sm"
        variant="light"
      />
      {showDropdown && (
        <>
          <div
            className="position-fixed"
            style={{
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              zIndex: 999,
            }}
            onClick={() => setShowDropdown(false)}
          ></div>
          <div
            className="position-absolute end-0 mt-1 bg-white border rounded shadow-lg"
            style={{
              minWidth: "320px",
              maxHeight: "450px",
              overflowY: "auto",
              zIndex: 1000,
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-2 border-bottom bg-light">
              <div className="d-flex justify-content-between align-items-center">
                <strong>
                  <i className="bi bi-people me-2"></i>
                  Danh sách người trực
                </strong>
                <button
                  className="btn-close btn-close-sm"
                  onClick={() => setShowDropdown(false)}
                ></button>
              </div>
            </div>
            <div
              className="p-2"
              style={{ maxHeight: "350px", overflowY: "auto" }}
            >
              {staff.length === 0 ? (
                <div className="text-muted text-center py-3">
                  <small>Chưa có dữ liệu người trực</small>
                </div>
              ) : (
                staff.map((person) => (
                  <div
                    key={person.id}
                    className="form-check py-2 border-bottom"
                  >
                    <input
                      className="form-check-input"
                      type="checkbox"
                      checked={person.status === "active"}
                      onChange={() => onToggleStatus(person.id)}
                      id={`staff-${person.id}`}
                    />
                    <label
                      className="form-check-label d-flex justify-content-between align-items-center w-100"
                      htmlFor={`staff-${person.id}`}
                      style={{ cursor: "pointer" }}
                    >
                      <div className="flex-grow-1">
                        <div className="fw-bold">{person.name}</div>
                        <small className="text-muted">
                          {person.position || "Bảo vệ"} • {person.shift || ""}
                        </small>
                      </div>
                      <span
                        className={`badge ms-2 ${
                          person.status === "active"
                            ? "bg-success"
                            : "bg-secondary"
                        }`}
                      >
                        {person.status === "active" ? "Hoạt động" : "Nghỉ"}
                      </span>
                    </label>
                  </div>
                ))
              )}
            </div>
            <div className="p-2 border-top bg-light">
              <button
                className="btn btn-primary btn-sm w-100"
                onClick={() => {
                  onSave();
                  setShowDropdown(false);
                }}
              >
                <i className="bi bi-save me-1"></i>
                Lưu thay đổi
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default StaffDropdown;
