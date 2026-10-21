import { Route, Routes } from "react-router-dom";
import AppLayout from "./layouts/AppLayout";
import DashboardPage from "./pages/DashboardPage";
import PlaceholderPage from "./pages/PlaceholderPage";

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<DashboardPage />} />
        <Route path="users" element={<PlaceholderPage title="User Management" />} />
        <Route path="clients" element={<PlaceholderPage title="Client Management" />} />
      </Route>
    </Routes>
  );
}
