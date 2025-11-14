import { HashRouter, Routes, Route } from 'react-router-dom';
import MainLayout from './layouts/MainLayout';
import Dashboard from './pages/Dashboard';
import Upload from './pages/Upload';
import Labeling from './pages/Labeling';
import Dataset from './pages/Dataset';

function App() {
  return (
    <HashRouter>
      <Routes>
        <Route path="/" element={<MainLayout />}>
          <Route index element={<Dashboard />} />
          <Route path="upload" element={<Upload />} />
          <Route path="labeling" element={<Labeling />} />
          <Route path="dataset" element={<Dataset />} />
        </Route>
      </Routes>
    </HashRouter>
  );
}

export default App;
