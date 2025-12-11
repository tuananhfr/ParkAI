import { useState, useEffect } from "react";
import { CENTRAL_URL } from "@/config";

/**
 * SubscriptionDevMode - Component quản lý thuê bao ở chế độ dev (có thể sửa/xóa)
 */
const SubscriptionDevMode = ({ apiUrl, onSave }) => {
  const [subscriptions, setSubscriptions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [formData, setFormData] = useState({
    plate_number: "",
    owner_name: "",
    type: "company",
    status: "active",
    start_date: "",
    end_date: "",
    phone: "",
    note: "",
  });

  useEffect(() => {
    fetchSubscriptions();
  }, [apiUrl]);

  const fetchSubscriptions = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch(`${CENTRAL_URL}/api/subscriptions`);
      const data = await response.json();
      if (data.success) {
        setSubscriptions(data.subscriptions || []);
      } else {
        setError(data.error || "Không thể tải danh sách thuê bao");
      }
    } catch (err) {
      setError("Không thể kết nối đến server");
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = (sub) => {
    setEditingId(sub.id);
    setFormData({
      plate_number: sub.plate_number || "",
      owner_name: sub.owner_name || "",
      type: sub.type || "company",
      status: sub.status || "active",
      start_date: sub.start_date || "",
      end_date: sub.end_date || "",
      phone: sub.phone || "",
      note: sub.note || "",
    });
    setShowAddForm(false);
  };

  const handleAdd = () => {
    setEditingId(null);
    setFormData({
      plate_number: "",
      owner_name: "",
      type: "company",
      status: "active",
      start_date: "",
      end_date: "",
      phone: "",
      note: "",
    });
    setShowAddForm(true);
  };

  const handleDelete = (id) => {
    if (window.confirm("Bạn có chắc muốn xóa thuê bao này?")) {
      setSubscriptions(subscriptions.filter((sub) => sub.id !== id));
    }
  };

  const handleSaveForm = () => {
    if (!formData.plate_number.trim()) {
      alert("Vui lòng nhập biển số xe");
      return;
    }

    if (editingId) {
      //Update existing
      setSubscriptions(
        subscriptions.map((sub) =>
          sub.id === editingId
            ? {
                ...sub,
                ...formData,
              }
            : sub
        )
      );
      setEditingId(null);
    } else {
      //Add new
      const maxId =
        subscriptions.length > 0
          ? Math.max(...subscriptions.map((s) => s.id || 0))
          : 0;
      setSubscriptions([
        ...subscriptions,
        {
          id: maxId + 1,
          ...formData,
        },
      ]);
      setShowAddForm(false);
    }
    setFormData({
      plate_number: "",
      owner_name: "",
      type: "company",
      status: "active",
      start_date: "",
      end_date: "",
      phone: "",
      note: "",
    });
  };

  const handleSaveToServer = async () => {
    try {
      const response = await fetch(`${CENTRAL_URL}/api/subscriptions`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ subscriptions }),
      });
      const data = await response.json();
      if (data.success) {
        alert("Đã lưu thành công!");
        fetchSubscriptions();
        if (onSave) onSave();
      } else {
        alert(`Lỗi: ${data.error || "Không thể lưu"}`);
      }
    } catch (err) {
      alert("Không thể kết nối đến server");
    }
  };

  const getTypeLabel = (type) => {
    switch (type) {
      case "company":
        return "Thẻ công ty";
      case "monthly":
        return "Thẻ tháng";
      case "regular":
        return "Khách lẻ";
      default:
        return type;
    }
  };

  const getTypeBadge = (type) => {
    switch (type) {
      case "company":
        return "bg-primary";
      case "monthly":
        return "bg-info";
      case "regular":
        return "bg-warning";
      default:
        return "bg-secondary";
    }
  };

  if (loading) {
    return (
      <div className="text-center py-3">
        <div className="spinner-border spinner-border-sm text-primary"></div>
        <small className="d-block mt-2 text-muted">Đang tải...</small>
      </div>
    );
  }

  if (error) {
    return (
      <div className="alert alert-warning">
        <i className="bi bi-exclamation-triangle me-2"></i>
        {error}
      </div>
    );
  }

  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-3">
        <small className="text-muted">
          <i className="bi bi-info-circle me-1"></i>
          Tổng số: {subscriptions.length} thuê bao
        </small>
        <button
          className="btn btn-sm btn-success"
          onClick={handleAdd}
          disabled={showAddForm || editingId !== null}
        >
          <i className="bi bi-plus-circle me-1"></i>
          Thêm mới
        </button>
      </div>

      {showAddForm && (
        <div className="card mb-3 border-success">
          <div className="card-header bg-success text-white">
            <strong>Thêm thuê bao mới</strong>
          </div>
          <div className="card-body">
            <div className="row g-2">
              <div className="col-md-6">
                <label className="form-label small">Biển số xe *</label>
                <input
                  type="text"
                  className="form-control form-control-sm"
                  value={formData.plate_number}
                  onChange={(e) =>
                    setFormData({ ...formData, plate_number: e.target.value })
                  }
                  placeholder="30A12345"
                />
              </div>
              <div className="col-md-6">
                <label className="form-label small">Tên chủ xe</label>
                <input
                  type="text"
                  className="form-control form-control-sm"
                  value={formData.owner_name}
                  onChange={(e) =>
                    setFormData({ ...formData, owner_name: e.target.value })
                  }
                  placeholder="Nguyễn Văn A"
                />
              </div>
              <div className="col-md-4">
                <label className="form-label small">Loại</label>
                <select
                  className="form-select form-select-sm"
                  value={formData.type}
                  onChange={(e) =>
                    setFormData({ ...formData, type: e.target.value })
                  }
                >
                  <option value="company">Thẻ công ty</option>
                  <option value="monthly">Thẻ tháng</option>
                  <option value="regular">Khách lẻ</option>
                </select>
              </div>
              <div className="col-md-4">
                <label className="form-label small">Trạng thái</label>
                <select
                  className="form-select form-select-sm"
                  value={formData.status}
                  onChange={(e) =>
                    setFormData({ ...formData, status: e.target.value })
                  }
                >
                  <option value="active">Hoạt động</option>
                  <option value="inactive">Nghỉ</option>
                </select>
              </div>
              <div className="col-md-4">
                <label className="form-label small">Số điện thoại</label>
                <input
                  type="text"
                  className="form-control form-control-sm"
                  value={formData.phone}
                  onChange={(e) =>
                    setFormData({ ...formData, phone: e.target.value })
                  }
                  placeholder="0901234567"
                />
              </div>
              {(formData.type === "company" || formData.type === "monthly") && (
                <>
                  <div className="col-md-6">
                    <label className="form-label small">Ngày bắt đầu</label>
                    <input
                      type="date"
                      className="form-control form-control-sm"
                      value={formData.start_date}
                      onChange={(e) =>
                        setFormData({ ...formData, start_date: e.target.value })
                      }
                    />
                  </div>
                  <div className="col-md-6">
                    <label className="form-label small">Ngày kết thúc</label>
                    <input
                      type="date"
                      className="form-control form-control-sm"
                      value={formData.end_date}
                      onChange={(e) =>
                        setFormData({ ...formData, end_date: e.target.value })
                      }
                    />
                  </div>
                </>
              )}
              <div className="col-12">
                <label className="form-label small">Ghi chú</label>
                <input
                  type="text"
                  className="form-control form-control-sm"
                  value={formData.note}
                  onChange={(e) =>
                    setFormData({ ...formData, note: e.target.value })
                  }
                  placeholder="Ghi chú"
                />
              </div>
            </div>
            <div className="mt-3">
              <button
                className="btn btn-sm btn-primary me-2"
                onClick={handleSaveForm}
              >
                <i className="bi bi-check-circle me-1"></i>
                Lưu
              </button>
              <button
                className="btn btn-sm btn-secondary"
                onClick={() => {
                  setShowAddForm(false);
                  setFormData({
                    plate_number: "",
                    owner_name: "",
                    type: "company",
                    status: "active",
                    start_date: "",
                    end_date: "",
                    phone: "",
                    note: "",
                  });
                }}
              >
                Hủy
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="table-responsive">
        <table className="table table-sm table-striped table-hover">
          <thead>
            <tr>
              <th>ID</th>
              <th>Biển số</th>
              <th>Chủ xe</th>
              <th>Loại</th>
              <th>SĐT</th>
              <th>Trạng thái</th>
              <th>Thao tác</th>
            </tr>
          </thead>
          <tbody>
            {subscriptions.map((sub) =>
              editingId === sub.id ? (
                <tr key={sub.id} className="table-warning">
                  <td colSpan="7">
                    <div className="row g-2">
                      <div className="col-md-6">
                        <label className="form-label small">Biển số xe *</label>
                        <input
                          type="text"
                          className="form-control form-control-sm"
                          value={formData.plate_number}
                          onChange={(e) =>
                            setFormData({
                              ...formData,
                              plate_number: e.target.value,
                            })
                          }
                        />
                      </div>
                      <div className="col-md-6">
                        <label className="form-label small">Tên chủ xe</label>
                        <input
                          type="text"
                          className="form-control form-control-sm"
                          value={formData.owner_name}
                          onChange={(e) =>
                            setFormData({
                              ...formData,
                              owner_name: e.target.value,
                            })
                          }
                        />
                      </div>
                      <div className="col-md-4">
                        <label className="form-label small">Loại</label>
                        <select
                          className="form-select form-select-sm"
                          value={formData.type}
                          onChange={(e) =>
                            setFormData({ ...formData, type: e.target.value })
                          }
                        >
                          <option value="company">Thẻ công ty</option>
                          <option value="monthly">Thẻ tháng</option>
                          <option value="regular">Khách lẻ</option>
                        </select>
                      </div>
                      <div className="col-md-4">
                        <label className="form-label small">Trạng thái</label>
                        <select
                          className="form-select form-select-sm"
                          value={formData.status}
                          onChange={(e) =>
                            setFormData({
                              ...formData,
                              status: e.target.value,
                            })
                          }
                        >
                          <option value="active">Hoạt động</option>
                          <option value="inactive">Nghỉ</option>
                        </select>
                      </div>
                      <div className="col-md-4">
                        <label className="form-label small">
                          Số điện thoại
                        </label>
                        <input
                          type="text"
                          className="form-control form-control-sm"
                          value={formData.phone}
                          onChange={(e) =>
                            setFormData({ ...formData, phone: e.target.value })
                          }
                        />
                      </div>
                      {(formData.type === "company" ||
                        formData.type === "monthly") && (
                        <>
                          <div className="col-md-6">
                            <label className="form-label small">
                              Ngày bắt đầu
                            </label>
                            <input
                              type="date"
                              className="form-control form-control-sm"
                              value={formData.start_date}
                              onChange={(e) =>
                                setFormData({
                                  ...formData,
                                  start_date: e.target.value,
                                })
                              }
                            />
                          </div>
                          <div className="col-md-6">
                            <label className="form-label small">
                              Ngày kết thúc
                            </label>
                            <input
                              type="date"
                              className="form-control form-control-sm"
                              value={formData.end_date}
                              onChange={(e) =>
                                setFormData({
                                  ...formData,
                                  end_date: e.target.value,
                                })
                              }
                            />
                          </div>
                        </>
                      )}
                      <div className="col-12">
                        <label className="form-label small">Ghi chú</label>
                        <input
                          type="text"
                          className="form-control form-control-sm"
                          value={formData.note}
                          onChange={(e) =>
                            setFormData({ ...formData, note: e.target.value })
                          }
                        />
                      </div>
                      <div className="col-12">
                        <button
                          className="btn btn-sm btn-primary me-2"
                          onClick={handleSaveForm}
                        >
                          <i className="bi bi-check-circle me-1"></i>
                          Lưu
                        </button>
                        <button
                          className="btn btn-sm btn-secondary"
                          onClick={() => {
                            setEditingId(null);
                            setFormData({
                              plate_number: "",
                              owner_name: "",
                              type: "company",
                              status: "active",
                              start_date: "",
                              end_date: "",
                              phone: "",
                              note: "",
                            });
                          }}
                        >
                          Hủy
                        </button>
                      </div>
                    </div>
                  </td>
                </tr>
              ) : (
                <tr key={sub.id}>
                  <td>{sub.id}</td>
                  <td>
                    <strong>{sub.plate_number}</strong>
                  </td>
                  <td>{sub.owner_name || "-"}</td>
                  <td>
                    <span className={`badge ${getTypeBadge(sub.type)}`}>
                      {getTypeLabel(sub.type)}
                    </span>
                  </td>
                  <td>{sub.phone || "-"}</td>
                  <td>
                    <span
                      className={`badge ${
                        sub.status === "active" ? "bg-success" : "bg-secondary"
                      }`}
                    >
                      {sub.status === "active" ? "Hoạt động" : "Nghỉ"}
                    </span>
                  </td>
                  <td>
                    <button
                      className="btn btn-sm btn-outline-primary me-1"
                      onClick={() => handleEdit(sub)}
                      title="Sửa"
                    >
                      <i className="bi bi-pencil"></i>
                    </button>
                    <button
                      className="btn btn-sm btn-outline-danger"
                      onClick={() => handleDelete(sub.id)}
                      title="Xóa"
                    >
                      <i className="bi bi-trash"></i>
                    </button>
                  </td>
                </tr>
              )
            )}
          </tbody>
        </table>
      </div>

      <div className="mt-3 d-flex justify-content-end">
        <button className="btn btn-primary btn-sm" onClick={handleSaveToServer}>
          <i className="bi bi-save me-1"></i>
          Lưu vào file JSON
        </button>
      </div>
    </div>
  );
};

export default SubscriptionDevMode;
