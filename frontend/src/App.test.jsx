import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import App from "./App";
import { AuthProvider } from "./hooks/AuthContext";
import * as authService from "./services/authService";
import { loginSchema } from "./schemas/authSchemas";

vi.mock("./services/authService");
vi.mock("./services/healthService", () => ({ getReadiness: () => Promise.resolve({ status: "ok" }) }));

const session = (role) => ({ csrf_token: "t", user: { id: 1, full_name: "Ann", employee_id: "EMP0001", role } });
const renderAt = (path) => render(<MemoryRouter initialEntries={[path]}><AuthProvider><App /></AuthProvider></MemoryRouter>);

test("login schema validates required fields", () => {
  expect(loginSchema.safeParse({ identifier: " ", password: "" }).success).toBe(false);
  expect(loginSchema.safeParse({ identifier: "EMP0001", password: "x" }).success).toBe(true);
});

test("unauthenticated user is redirected to login", async () => {
  authService.getMe.mockRejectedValue({ status: 401 });
  renderAt("/users");
  expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
});

test("login shows field errors and generic server error", async () => {
  authService.getMe.mockRejectedValue({ status: 401 });
  authService.login.mockRejectedValue({ status: 401, message: "Invalid credentials." });
  renderAt("/login");
  await userEvent.click(await screen.findByRole("button", { name: /sign in/i }));
  expect(await screen.findByText("Enter your Employee ID or email.")).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText(/employee id or email/i), "EMP0001");
  await userEvent.type(screen.getByLabelText("Password"), "wrong");
  await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
  expect(await screen.findByRole("alert")).toHaveTextContent("incorrect");
});

test("admin sees admin navigation", async () => {
  authService.getMe.mockResolvedValue(session("ADMIN"));
  renderAt("/");
  expect(await screen.findByRole("link", { name: /user management/i })).toBeInTheDocument();
});

test("supervisor has no admin nav and is redirected from admin routes", async () => {
  authService.getMe.mockResolvedValue(session("SUPERVISOR"));
  renderAt("/users");
  await waitFor(() => expect(screen.getByRole("heading", { name: "Dashboard" })).toBeInTheDocument());
  expect(screen.queryByRole("link", { name: /user management/i })).toBeNull();
});
