import { Route, Routes } from "react-router-dom";
import AppLayout from "./layouts/AppLayout";
import ProtectedRoute from "./components/ProtectedRoute";
import DashboardPage from "./pages/DashboardPage";
import LoginPage from "./pages/LoginPage";
import UserListPage from "./pages/UserListPage";
import CreateUserPage from "./pages/CreateUserPage";
import UserDetailPage from "./pages/UserDetailPage";
import ActivatePage from "./pages/ActivatePage";
import ClientListPage from "./pages/ClientListPage";
import CreateClientPage from "./pages/CreateClientPage";
import ClientDetailPage from "./pages/ClientDetailPage";

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
            <Route path="clients" element={<ClientListPage />} />
            <Route path="clients/new" element={<CreateClientPage />} />
            <Route path="clients/:id" element={<ClientDetailPage />} />
          </Route>
        </Route>
      </Route>
    </Routes>
  );
}
