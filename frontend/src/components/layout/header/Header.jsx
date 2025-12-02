import { useState } from "react";
import StaffDropdown from "./StaffDropdown";
import HistoryModal from "./HistoryModal";
import SettingsModal from "@/components/settings/SettingsModal";
import InfoHeader from "./InfoHeader";
import DynamicButton from "@/components/button/DynamicButton";
/**
 * Header - Component header với stats và action buttons
 * Quản lý HistoryModal và SettingsModal
 */
const Header = ({
  stats,
  staff,
  onFetchStaff,
  onToggleStaffStatus,
  onSaveStaffChanges,
  historyKey,
  onFetchCameras,
}) => {
  const [showHistoryModal, setShowHistoryModal] = useState(false);
  const [showSettingsModal, setShowSettingsModal] = useState(false);

  return (
    <>
      <div className="bg-primary text-white py-1 px-2 d-flex justify-content-between align-items-center">
        <InfoHeader stats={stats} />

        <div className="d-flex gap-2">
          <DynamicButton
            icon="bi-clock-history"
            text="Xem lịch sử"
            onClick={() => setShowHistoryModal(true)}
            size="sm"
            variant="light"
          />

          <HistoryModal
            show={showHistoryModal}
            onClose={() => setShowHistoryModal(false)}
            historyKey={historyKey}
          />

          <StaffDropdown
            staff={staff}
            onFetchStaff={onFetchStaff}
            onToggleStatus={onToggleStaffStatus}
            onSave={onSaveStaffChanges}
          />

          <DynamicButton
            icon="bi-gear-fill"
            text="Cài đặt"
            onClick={() => setShowSettingsModal(true)}
            size="sm"
            variant="light"
          />
        </div>
      </div>

      <SettingsModal
        show={showSettingsModal}
        onClose={() => setShowSettingsModal(false)}
        onSaveSuccess={onFetchCameras}
      />
    </>
  );
};

export default Header;
