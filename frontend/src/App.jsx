import { Route, Routes } from "react-router-dom";
import AppLayout from "./layouts/AppLayout";
import ProtectedRoute from "./components/ProtectedRoute";
import DashboardPage from "./pages/DashboardPage";
import LoginPage from "./pages/LoginPage";
import PlaceholderPage from "./pages/PlaceholderPage";

export default function App() {
  return (
    <Routes>
      <Route path="login" element={<LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route index element={<DashboardPage />} />
          <Route element={<ProtectedRoute roles={["ADMIN"]} />}>
            <Route path="users" element={<PlaceholderPage title="User Management" />} />
            <Route path="clients" element={<PlaceholderPage title="Client Management" />} />
          </Route>
        </Route>
      </Route>
    </Routes>
  );
}
