import { Route, Routes } from "react-router-dom";
import AppLayout from "./layouts/AppLayout";
import ProtectedRoute from "./components/ProtectedRoute";
import DashboardPage from "./pages/DashboardPage";
import LoginPage from "./pages/LoginPage";
import PlaceholderPage from "./pages/PlaceholderPage";
import UserListPage from "./pages/UserListPage";
import CreateUserPage from "./pages/CreateUserPage";
import UserDetailPage from "./pages/UserDetailPage";
import ActivatePage from "./pages/ActivatePage";

export default function App() {
  return (
    <Routes>
      <Route path="login" element={<LoginPage />} />
      <Route path="activate" element={<ActivatePage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route index element={<DashboardPage />} />
          <Route element={<ProtectedRoute roles={["ADMIN"]} />}>
            <Route path="users" element={<UserListPage />} />
            <Route path="users/new" element={<CreateUserPage />} />
            <Route path="users/:id" element={<UserDetailPage />} />
            <Route path="clients" element={<PlaceholderPage title="Client Management" />} />
          </Route>
        </Route>
      </Route>
    </Routes>
  );
}
