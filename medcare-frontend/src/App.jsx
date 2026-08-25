import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/layout/Layout';
import Dashboard from './pages/Dashboard';
import Inventory from './pages/Inventory';
import DemandForecast from './pages/DemandForecast';
import Replenishment from './pages/Replenishment';
import Alerts from './pages/Alerts';
import Warehouses from './pages/Warehouses';
import Reports from './pages/Reports';
import ScenarioSimulator from './pages/ScenarioSimulator';
import Settings from './pages/Settings';
import UserManagement from './pages/UserManagement';
import Login from './pages/Login';
import ProtectedRoute from './components/auth/ProtectedRoute';
import { AuthProvider } from './context/AuthContext';
import { ControlTowerProvider } from './context/ControlTowerContext';

export default function App() {
  return (
    <AuthProvider>
      <ControlTowerProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            
            <Route
              element={
                <ProtectedRoute>
                  <Layout />
                </ProtectedRoute>
              }
            >
              <Route path="/" element={<Dashboard />} />
              <Route path="/inventory" element={<Inventory />} />
              <Route path="/demand-forecast" element={<DemandForecast />} />
              <Route path="/replenishment" element={<Replenishment />} />
              <Route path="/alerts" element={<Alerts />} />
              <Route path="/warehouses" element={<Warehouses />} />
              <Route path="/reports" element={<Reports />} />
              <Route path="/scenario-simulator" element={<ScenarioSimulator />} />
              <Route
                path="/users"
                element={
                  <ProtectedRoute requireAdmin={true}>
                    <UserManagement />
                  </ProtectedRoute>
                }
              />
              <Route path="/settings" element={<Settings />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </ControlTowerProvider>
    </AuthProvider>
  );
}