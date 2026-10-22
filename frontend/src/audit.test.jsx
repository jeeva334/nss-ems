import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { vi, beforeEach } from "vitest";
import App from "./App";
import { AuthProvider } from "./hooks/AuthContext";
import * as authService from "./services/authService";
import * as audit from "./services/auditService";

vi.mock("./services/authService");
vi.mock("./services/auditService");

const session = (role) => ({ csrf_token: "t", user: { id: 1, full_name: "Root", employee_id: "EMP0001", role } });
const ev = (o = {}) => ({ id: 1, timestamp: "2026-10-01T10:00:00Z", actor: { id: 1, employee_id: "EMP0001", full_name: "Root" },
  action: "user.create", target_type: "user", target_id: "5", metadata: { role: "MANAGER", password: "[redacted]" }, correlation_id: "req-1234567", ...o });
const page = (items, total = items.length) => ({ items, total, page: 1, page_size: 25 });
const renderAt = (p) => render(<MemoryRouter initialEntries={[p]}><AuthProvider><App /></AuthProvider></MemoryRouter>);

beforeEach(() => { vi.resetAllMocks(); authService.getMe.mockResolvedValue(session("ADMIN")); });

test("shows events with actor, target, redacted metadata and request id", async () => {
  audit.listAuditLogs.mockResolvedValue(page([ev(), ev({ id: 2, actor: null, action: "auth.login_failed", target_type: null })]));
  renderAt("/audit");
  expect(await screen.findByText("user.create")).toBeInTheDocument();
  expect(screen.getByText("Root (EMP0001)")).toBeInTheDocument();
  expect(screen.getByText("System / anonymous")).toBeInTheDocument();
  expect(screen.getAllByText(/\[redacted\]/).length).toBe(2);
  expect(screen.getAllByText("Request ID: req-1234567").length).toBe(2);
});

test("category and date filters go to the API; page resets to 1", async () => {
  audit.listAuditLogs.mockResolvedValue(page([ev()], 60));
  renderAt("/audit");
  await screen.findByText("user.create");
  await userEvent.selectOptions(screen.getByLabelText("Category"), "auth.");
  await waitFor(() => expect(audit.listAuditLogs).toHaveBeenLastCalledWith(expect.objectContaining({ action: "auth.", page: 1 })));
  await userEvent.type(screen.getByLabelText("From"), "2026-10-01");
  await waitFor(() => {
    const last = audit.listAuditLogs.mock.calls.at(-1)[0];
    expect(last.action).toBe("auth.");
    expect(last.date_from).toMatch(/^2026-10-0[01]T/);
  });
});

test("paginates on the server", async () => {
  audit.listAuditLogs.mockResolvedValue(page([ev()], 60));
  renderAt("/audit");
  await screen.findByText("Showing 1–25 of 60");
  await userEvent.click(screen.getByRole("button", { name: "Next" }));
  await waitFor(() => expect(audit.listAuditLogs).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2 })));
});

test("empty and error states", async () => {
  audit.listAuditLogs.mockRejectedValueOnce({ status: 503, message: "The service is temporarily unavailable." }).mockResolvedValueOnce(page([]));
  renderAt("/audit");
  expect(await screen.findByRole("alert")).toHaveTextContent("temporarily unavailable");
  await userEvent.click(screen.getByRole("button", { name: "Retry" }));
  expect(await screen.findByText(/No audit events match/)).toBeInTheDocument();
});

test("non-admins have no Audit Log navigation and cannot open the page", async () => {
  authService.getMe.mockResolvedValue(session("MANAGER"));
  renderAt("/audit");
  await waitFor(() => expect(screen.getByRole("heading", { name: "Dashboard" })).toBeInTheDocument());
  expect(screen.queryByRole("link", { name: /audit log/i })).toBeNull();
  expect(audit.listAuditLogs).not.toHaveBeenCalled();
});
