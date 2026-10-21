import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { vi, beforeEach } from "vitest";
import App from "./App";
import { AuthProvider } from "./hooks/AuthContext";
import * as authService from "./services/authService";
import * as users from "./services/userService";
import { activateSchema, createUserSchema } from "./schemas/userSchemas";

vi.mock("./services/authService");
vi.mock("./services/userService");

const admin = { csrf_token: "t", user: { id: 1, full_name: "Root", employee_id: "EMP0001", role: "ADMIN" } };
const u = (o = {}) => ({ id: 2, employee_id: "EMP0002", full_name: "Asha Rao", email: "asha@example.com", mobile_number: "+919876543210",
  role: "SUPERVISOR", status: "ACTIVE", created_at: "2026-10-01T00:00:00Z", last_login_at: null, ...o });
const page = (items, total = items.length) => ({ items, total, page: 1, page_size: 20 });
const renderAt = (path) => render(<MemoryRouter initialEntries={[path]}><AuthProvider><App /></AuthProvider></MemoryRouter>);

beforeEach(() => { vi.resetAllMocks(); authService.getMe.mockResolvedValue(admin); });

test("schemas validate input", () => {
  const ok = { full_name: "Asha Rao", mobile_number: "98765 43210", email: "a@b.com", role: "MANAGER" };
  expect(createUserSchema.safeParse(ok).success).toBe(true);
  for (const bad of [{ mobile_number: "abc" }, { email: "nope" }, { role: "" }, { full_name: "A" }])
    expect(createUserSchema.safeParse({ ...ok, ...bad }).success).toBe(false);
  expect(activateSchema.safeParse({ password: "short1", confirm_password: "short1" }).success).toBe(false);
  expect(activateSchema.safeParse({ password: "LongPassword123", confirm_password: "Different12345" }).success).toBe(false);
  expect(activateSchema.safeParse({ password: "LongPassword123", confirm_password: "LongPassword123" }).success).toBe(true);
});

test("user list renders rows, searches and filters through the API", async () => {
  users.listUsers.mockResolvedValue(page([u(), u({ id: 3, employee_id: "EMP0003", full_name: "Ben Lee", status: "PENDING" })], 2));
  renderAt("/users");
  expect(await screen.findByText("EMP0002")).toBeInTheDocument();
  expect(within(screen.getByRole("table")).getByText("Pending")).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText("Search users"), "asha{enter}");
  await waitFor(() => expect(users.listUsers).toHaveBeenLastCalledWith(expect.objectContaining({ q: "asha", page: 1 })));
  await userEvent.selectOptions(screen.getByLabelText("Filter by role"), "MANAGER");
  await waitFor(() => expect(users.listUsers).toHaveBeenLastCalledWith(expect.objectContaining({ role: "MANAGER", q: "asha" })));
  await userEvent.selectOptions(screen.getByLabelText("Filter by status"), "ACTIVE");
  await waitFor(() => expect(users.listUsers).toHaveBeenLastCalledWith(expect.objectContaining({ status: "ACTIVE", role: "MANAGER" })));
});

test("pagination requests the next page from the server", async () => {
  users.listUsers.mockResolvedValue({ items: [u()], total: 45, page: 1, page_size: 20 });
  renderAt("/users");
  await screen.findByText("Showing 1–20 of 45");
  await userEvent.click(screen.getByRole("button", { name: "Next" }));
  await waitFor(() => expect(users.listUsers).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2 })));
});

test("empty and error states, with retry", async () => {
  users.listUsers.mockResolvedValueOnce(page([]));
  renderAt("/users");
  expect(await screen.findByText(/No users yet/)).toBeInTheDocument();
});

test("error state offers retry", async () => {
  users.listUsers.mockRejectedValueOnce({ status: 0, message: "Cannot reach the server." }).mockResolvedValueOnce(page([u()]));
  renderAt("/users");
  expect(await screen.findByRole("alert")).toHaveTextContent("Cannot reach the server.");
  await userEvent.click(screen.getByRole("button", { name: "Retry" }));
  expect(await screen.findByText("EMP0002")).toBeInTheDocument();
});

test("Create User button opens the separate create page, which has no Employee ID input", async () => {
  users.listUsers.mockResolvedValue(page([u()]));
  renderAt("/users");
  await userEvent.click(await screen.findByRole("button", { name: /create user/i }));
  expect(await screen.findByRole("heading", { name: "Create User" })).toBeInTheDocument();
  expect(screen.queryByLabelText(/employee id/i)).toBeNull();
  expect(screen.getByRole("button", { name: /CREATE USER & SEND INVITATION/ })).toBeInTheDocument();
});

async function fillCreate() {
  await userEvent.type(await screen.findByLabelText("Full name"), "Asha Rao");
  await userEvent.type(screen.getByLabelText("Mobile number"), "9876543210");
  await userEvent.type(screen.getByLabelText("Email address"), "asha@example.com");
  await userEvent.selectOptions(screen.getByLabelText("Role"), "SUPERVISOR");
}

test("create form shows field errors before calling the API", async () => {
  renderAt("/users/new");
  await userEvent.click(await screen.findByRole("button", { name: /CREATE USER/ }));
  expect(await screen.findByText("Enter the full name.")).toBeInTheDocument();
  expect(screen.getByText("Select a role.")).toBeInTheDocument();
  expect(users.createUser).not.toHaveBeenCalled();
});

test("duplicate email error appears beside the email field", async () => {
  users.createUser.mockRejectedValue({ status: 409, code: "duplicate_email", message: "dup", fields: [] });
  renderAt("/users/new");
  await fillCreate();
  await userEvent.click(screen.getByRole("button", { name: /CREATE USER/ }));
  expect(await screen.findByText("A user with this email already exists.")).toBeInTheDocument();
});

test("double submit calls the API once and success shows the generated Employee ID", async () => {
  let resolve;
  users.createUser.mockReturnValue(new Promise((r) => { resolve = r; }));
  renderAt("/users/new");
  await fillCreate();
  const btn = screen.getByRole("button", { name: /CREATE USER/ });
  await userEvent.dblClick(btn);
  expect(users.createUser).toHaveBeenCalledTimes(1);
  resolve({ user: u({ employee_id: "EMP0042" }), delivery: { status: "sent", provider: "resend" } });
  expect(await screen.findByText("EMP0042")).toBeInTheDocument();
  expect(screen.getByText(/accepted by the email provider/)).toBeInTheDocument();
});

test("failed email delivery is reported honestly", async () => {
  users.createUser.mockResolvedValue({ user: u(), delivery: { status: "failed", provider: "resend", error: "provider_http_503" } });
  renderAt("/users/new");
  await fillCreate();
  await userEvent.click(screen.getByRole("button", { name: /CREATE USER/ }));
  expect(await screen.findByRole("alert")).toHaveTextContent("could not be sent");
  expect(screen.queryByText(/accepted by the email provider/)).toBeNull();
});

const detail = (user, assignments, invitation = null) => users.getUser.mockResolvedValue({ user, assignments, invitation });

test("admin detail has no assignment controls", async () => {
  detail(u({ role: "ADMIN", id: 5 }), {});
  renderAt("/users/5");
  expect(await screen.findByText("Administrative profile")).toBeInTheDocument();
  expect(screen.queryByText("Assigned clients")).toBeNull();
});

test("manager detail lists clients and supervisors", async () => {
  detail(u({ role: "MANAGER", id: 6 }), { clients: [{ id: 1, client_name: "Acme", client_code: "C1" }],
    supervisors: [{ id: 9, full_name: "Sam Sup", employee_id: "EMP0009" }] });
  renderAt("/users/6");
  expect(await screen.findByText("Assigned clients")).toBeInTheDocument();
  expect(screen.getByText(/Acme/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Sam Sup" })).toBeInTheDocument();
});

test("supervisor detail shows read-only manager and client", async () => {
  detail(u({ id: 7 }), { manager: { id: 6, full_name: "Mia Mgr", employee_id: "EMP0006" }, client: { client_name: "Acme", client_code: "C1" } });
  renderAt("/users/7");
  expect(await screen.findByText("Manager (read-only)")).toBeInTheDocument();
  expect(screen.getByText("Mia Mgr (EMP0006)")).toBeInTheDocument();
  expect(screen.queryByRole("combobox")).toBeNull();
});

test("deactivation requires confirmation", async () => {
  detail(u({ id: 7 }), { manager: null, client: null });
  users.setUserStatus.mockResolvedValue(u({ status: "INACTIVE" }));
  renderAt("/users/7");
  await userEvent.click(await screen.findByRole("button", { name: "Deactivate account" }));
  expect(users.setUserStatus).not.toHaveBeenCalled();
  const dlg = screen.getByRole("dialog");
  await userEvent.click(within(dlg).getByRole("button", { name: "Deactivate" }));
  await waitFor(() => expect(users.setUserStatus).toHaveBeenCalledWith(7, "INACTIVE"));
});

test("pending user can resend invitation; delivery failure is surfaced", async () => {
  detail(u({ id: 8, status: "PENDING" }), { manager: null, client: null },
    { state: "SEND_FAILED", expires_at: "2026-10-22T00:00:00Z", send_error: "provider_http_503" });
  users.sendInvitation.mockResolvedValue({ delivery: { status: "failed", provider: "resend", error: "provider_http_503" } });
  renderAt("/users/8");
  await userEvent.click(await screen.findByRole("button", { name: "Resend invitation" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("email delivery failed");
});

test("activation page reads token from the URL fragment and activates", async () => {
  window.history.pushState(null, "", "/activate#token=" + "a".repeat(40));
  users.activateAccount.mockResolvedValue({});
  renderAt("/activate");
  await userEvent.type(await screen.findByLabelText("New password"), "LongPassword123");
  await userEvent.type(screen.getByLabelText("Confirm password"), "LongPassword123");
  await userEvent.click(screen.getByRole("button", { name: "Activate account" }));
  await waitFor(() => expect(users.activateAccount).toHaveBeenCalledWith("a".repeat(40), "LongPassword123", "LongPassword123"));
  expect(await screen.findByText("Account activated")).toBeInTheDocument();
  expect(window.location.hash).toBe("");
});
