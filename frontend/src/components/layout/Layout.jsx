import Header from "./header/Header";
import Body from "./Body";

/**
 * Layout - Main layout component (header + body)
 */
const Layout = ({
  stats,
  cameras,
  staff,
  onHistoryUpdate,
  onFetchStaff,
  onToggleStaffStatus,
  onSaveStaffChanges,
  historyKey,
  onFetchCameras,
}) => {
  return (
    <div
      className="d-flex flex-column"
      style={{ width: "100vw", height: "100vh", overflow: "hidden" }}
    >
      <Header
        stats={stats}
        staff={staff}
        onFetchStaff={onFetchStaff}
        onToggleStaffStatus={onToggleStaffStatus}
        onSaveStaffChanges={onSaveStaffChanges}
        historyKey={historyKey}
        onFetchCameras={onFetchCameras}
      />
      <Body cameras={cameras} onHistoryUpdate={onHistoryUpdate} />
    </div>
  );
};

export default Layout;
