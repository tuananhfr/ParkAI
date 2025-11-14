import { Outlet } from 'react-router-dom';
import Sidebar from '../components/Sidebar';

const MainLayout = () => {
  return (
    <div className="d-flex">
      <Sidebar />
      <div className="flex-grow-1 p-4" style={{ backgroundColor: '#f8f9fa', minHeight: '100vh' }}>
        <Outlet />
      </div>
    </div>
  );
};

export default MainLayout;
