import { useState } from "react";
import useCameras from "./hooks/useCameras";
import useStats from "./hooks/useStats";
import useStaff from "./hooks/useStaff";
import Layout from "./components/layout/Layout";

function App() {
  const [historyKey, setHistoryKey] = useState(0);

  // Custom hooks
  const { cameras, fetchCameras } = useCameras();
  const { stats } = useStats();
  const { staff, fetchStaff, toggleStaffStatus, saveStaffChanges } = useStaff();

  const handleHistoryUpdate = () => {
    setHistoryKey((prev) => prev + 1);
  };

  const handleSaveStaffChanges = async () => {
    await saveStaffChanges();
  };

  return (
    <Layout
      stats={stats}
      cameras={cameras}
      staff={staff}
                  onHistoryUpdate={handleHistoryUpdate}
      onFetchStaff={fetchStaff}
      onToggleStaffStatus={toggleStaffStatus}
      onSaveStaffChanges={handleSaveStaffChanges}
      historyKey={historyKey}
      onFetchCameras={fetchCameras}
    />
  );
}

export default App;
