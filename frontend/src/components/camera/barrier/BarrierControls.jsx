/**
 * Component điều khiển barrier (nút đóng barrier)
 */
const BarrierControls = ({ barrierStatus, isOpening, onCloseBarrier }) => {
  return (
    <div className="d-flex gap-2 mt-2">
      <button
        className="btn btn-danger flex-fill"
        onClick={onCloseBarrier}
        disabled={isOpening || !barrierStatus.is_open}
        style={{ fontSize: "1rem", padding: "10px" }}
      >
        <i className="bi bi-door-closed-fill me-2"></i>
        Đóng barrier
      </button>
    </div>
  );
};

export default BarrierControls;
