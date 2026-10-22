import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { vi, beforeEach } from "vitest";
import App from "./App";
import { AuthProvider } from "./hooks/AuthContext";
import * as authService from "./services/authService";
import * as users from "./services/userService";
import * as clients from "./services/clientService";
import * as assign from "./services/assignmentService";
import { createClientSchema } from "./schemas/clientSchemas";

vi.mock("./services/authService");
vi.mock("./services/userService");
vi.mock("./services/clientService");
vi.mock("./services/assignmentService");

const admin = { csrf_token: "t", user: { id: 1, full_name: "Root", employee_id: "EMP0001", role: "ADMIN" } };
const mgr = (id, name) => ({ id, employee_id: `EMP000${id}`, full_name: name, role: "MANAGER", status: "ACTIVE" });
const client = (o = {}) => ({ id: 10, client_code: "ACME", client_name: "Acme Ltd", address: null, contact_name: null, contact_email: null,
  contact_phone: null, manager_id: null, manager: null, status: "ACTIVE", ...o });
const list = (items) => ({ items, total: items.length, page: 1, page_size: 20 });
const renderAt = (path) => render(<MemoryRouter initialEntries={[path]}><AuthProvider><App /></AuthProvider></MemoryRouter>);
const u = (o = {}) => ({ id: 7, employee_id: "EMP0007", full_name: "Sam Sup", email: "s@example.com", mobile_number: "1", role: "SUPERVISOR",
  status: "ACTIVE", created_at: "2026-10-01T00:00:00Z", last_login_at: null, ...o });

beforeEach(() => {
  vi.resetAllMocks();
  authService.getMe.mockResolvedValue(admin);
  users.listUsers.mockResolvedValue(list([]));
  clients.listClients.mockResolvedValue(list([]));
  assign.getAssignments.mockResolvedValue({ history: [], assignments: {} });
});

test("client schema validates", () => {
  const ok = { client_code: "acme-01", client_name: "Acme", address: "", contact_email: "", contact_phone: "" };
  expect(createClientSchema.safeParse(ok).success).toBe(true);
  expect(createClientSchema.safeParse({ ...ok, client_code: "!" }).success).toBe(false);
  expect(createClientSchema.safeParse({ ...ok, contact_email: "bad" }).success).toBe(false);
  expect(createClientSchema.safeParse({ ...ok, client_name: "A" }).success).toBe(false);
});

test("client list shows manager / unassigned, searches and opens create page", async () => {
  clients.listClients.mockResolvedValue(list([client({ manager: mgr(2, "Mia Mgr") }), client({ id: 11, client_code: "ZED", client_name: "Zed" })]));
  renderAt("/clients");
  expect(await screen.findByText("Mia Mgr")).toBeInTheDocument();
  expect(screen.getByText("Unassigned")).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText("Search clients"), "zed{enter}");
  await waitFor(() => expect(clients.listClients).toHaveBeenLastCalledWith(expect.objectContaining({ q: "zed", page: 1 })));
  await userEvent.click(screen.getByRole("button", { name: /create client/i }));
  expect(await screen.findByRole("heading", { name: "Create Client" })).toBeInTheDocument();
});

test("client list empty state", async () => {
  renderAt("/clients");
  expect(await screen.findByText(/No clients yet/)).toBeInTheDocument();
});

test("duplicate client code shown beside the field; success opens the client", async () => {
  clients.createClient.mockRejectedValueOnce({ status: 409, code: "duplicate_client_code", message: "dup", fields: [] });
  renderAt("/clients/new");
  await userEvent.type(await screen.findByLabelText("Client code"), "ACME");
  await userEvent.type(screen.getByLabelText("Client name"), "Acme Ltd");
  await userEvent.click(screen.getByRole("button", { name: "CREATE CLIENT" }));
  expect(await screen.findByText("A client with this code already exists.")).toBeInTheDocument();
  clients.createClient.mockResolvedValueOnce(client());
  clients.getClient.mockResolvedValue({ client: client(), supervisors: [] });
  await userEvent.click(screen.getByRole("button", { name: "CREATE CLIENT" }));
  expect(await screen.findByRole("heading", { name: "Acme Ltd" })).toBeInTheDocument();
});

describe("client detail", () => {
  test("assigning a first Manager offers only active managers and sends reassign=false", async () => {
    users.listUsers.mockResolvedValue(list([mgr(2, "Mia Mgr")]));
    clients.getClient.mockResolvedValue({ client: client(), supervisors: [] });
    clients.putClientManager.mockResolvedValue(client({ manager: mgr(2, "Mia Mgr") }));
    renderAt("/clients/10");
    await userEvent.selectOptions(await screen.findByLabelText("Manager"), "2");
    await userEvent.click(screen.getByRole("button", { name: "Assign Manager" }));
    await waitFor(() => expect(clients.putClientManager).toHaveBeenCalledWith(10, 2, false));
    expect(users.listUsers).toHaveBeenCalledWith(expect.objectContaining({ role: "MANAGER", status: "ACTIVE" }));
  });

  test("reassignment needs confirmation and sends reassign=true", async () => {
    users.listUsers.mockResolvedValue(list([mgr(2, "Mia Mgr"), mgr(3, "Noah Mgr")]));
    clients.getClient.mockResolvedValue({ client: client({ manager_id: 2, manager: mgr(2, "Mia Mgr") }), supervisors: [] });
    clients.putClientManager.mockResolvedValue(client());
    renderAt("/clients/10");
    const pick = await screen.findByLabelText("Manager");
    expect(within(pick).queryByText(/Mia Mgr/)).toBeNull(); // current manager is not offered
    await userEvent.selectOptions(pick, "3");
    await userEvent.click(screen.getByRole("button", { name: "Reassign Manager" }));
    expect(clients.putClientManager).not.toHaveBeenCalled();
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Reassign" }));
    await waitFor(() => expect(clients.putClientManager).toHaveBeenCalledWith(10, 3, true));
  });

  test("blocked reassignment names the affected Supervisors", async () => {
    users.listUsers.mockResolvedValue(list([mgr(3, "Noah Mgr")]));
    clients.getClient.mockResolvedValue({ client: client({ manager_id: 2, manager: mgr(2, "Mia Mgr") }), supervisors: [] });
    clients.putClientManager.mockRejectedValue({ status: 409, code: "has_dependent_assignments", message: "Move these Supervisors first.",
      details: { supervisors: [{ id: 7, employee_id: "EMP0007", full_name: "Sam Sup" }] } });
    renderAt("/clients/10");
    await userEvent.selectOptions(await screen.findByLabelText("Manager"), "3");
    await userEvent.click(screen.getByRole("button", { name: "Reassign Manager" }));
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Reassign" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Sam Sup (EMP0007)");
  });

  test("inactive client cannot be assigned a Manager", async () => {
    users.listUsers.mockResolvedValue(list([mgr(2, "Mia Mgr")]));
    clients.getClient.mockResolvedValue({ client: client({ status: "INACTIVE" }), supervisors: [] });
    renderAt("/clients/10");
    expect(await screen.findByLabelText("Manager")).toBeDisabled();
  });
});

describe("manager detail", () => {
  const managerDetail = (assignments) => users.getUser.mockResolvedValue({ user: u({ id: 2, role: "MANAGER" }), invitation: null, assignments });

  test("assigns an unassigned client, with no manager override", async () => {
    managerDetail({ clients: [], supervisors: [] });
    clients.listClients.mockResolvedValue(list([client({ id: 20, client_name: "Free Co", client_code: "FREE" })]));
    clients.putClientManager.mockResolvedValue(client());
    renderAt("/users/2");
    await userEvent.selectOptions(await screen.findByLabelText("Client to assign"), "20");
    await userEvent.click(screen.getByRole("button", { name: "Assign client" }));
    await waitFor(() => expect(clients.putClientManager).toHaveBeenCalledWith(20, 2, false));
    expect(clients.listClients).toHaveBeenCalledWith(expect.objectContaining({ unassigned: true, status: "ACTIVE" }));
  });

  test("removing a client and unmapping a Supervisor both require confirmation", async () => {
    managerDetail({ clients: [{ id: 5, client_name: "Acme", client_code: "A1" }], supervisors: [{ id: 9, full_name: "Sam Sup", employee_id: "EMP0009" }] });
    clients.putClientManager.mockResolvedValue(client());
    assign.mapSupervisorManager.mockResolvedValue({});
    renderAt("/users/2");
    await userEvent.click(await screen.findByRole("button", { name: "Remove Acme" }));
    expect(clients.putClientManager).not.toHaveBeenCalled();
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Remove" }));
    await waitFor(() => expect(clients.putClientManager).toHaveBeenCalledWith(5, null, false));
    await userEvent.click(await screen.findByRole("button", { name: "Unmap Sam Sup" }));
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Unmap" }));
    await waitFor(() => expect(assign.mapSupervisorManager).toHaveBeenCalledWith(9, null, false));
  });

  test("maps an existing unmapped Supervisor (inactive ones are not offered)", async () => {
    managerDetail({ clients: [], supervisors: [] });
    users.listUsers.mockResolvedValue(list([u({ id: 30, full_name: "Free Sup", employee_id: "EMP0030" }), u({ id: 31, full_name: "Gone Sup", status: "INACTIVE" })]));
    assign.mapSupervisorManager.mockResolvedValue({});
    renderAt("/users/2");
    const sel = await screen.findByLabelText("Supervisor to map");
    await waitFor(() => expect(within(sel).getByText(/Free Sup/)).toBeInTheDocument());
    expect(within(sel).queryByText(/Gone Sup/)).toBeNull();
    await userEvent.selectOptions(sel, "30");
    await userEvent.click(screen.getByRole("button", { name: "Map supervisor" }));
    await waitFor(() => expect(assign.mapSupervisorManager).toHaveBeenCalledWith(30, 2, false));
    expect(users.listUsers).toHaveBeenCalledWith(expect.objectContaining({ role: "SUPERVISOR", mapped: false }));
  });
});

describe("supervisor detail", () => {
  const supDetail = (a) => users.getUser.mockResolvedValue({ user: u(), invitation: null, assignments: a });
  const mapped = { manager: { id: 2, employee_id: "EMP0002", full_name: "Mia Mgr" }, client: null };

  test("client options come from the mapped Manager and the Manager id is never sent", async () => {
    supDetail(mapped);
    clients.listClients.mockResolvedValue(list([client({ id: 20, client_name: "Mia Client", client_code: "MC" })]));
    assign.assignSupervisorClient.mockResolvedValue({});
    renderAt("/users/7");
    const sel = await screen.findByLabelText("Client");
    await waitFor(() => expect(within(sel).getByText(/Mia Client/)).toBeInTheDocument());
    expect(clients.listClients).toHaveBeenCalledWith(expect.objectContaining({ manager_id: 2, status: "ACTIVE" }));
    await userEvent.selectOptions(sel, "20");
    await userEvent.click(screen.getByRole("button", { name: "Assign client" }));
    await waitFor(() => expect(assign.assignSupervisorClient).toHaveBeenCalledWith(7, 20));
    expect(assign.assignSupervisorClient.mock.calls[0]).toHaveLength(2);
  });

  test("without a Manager mapping the client control is unavailable", async () => {
    supDetail({ manager: null, client: null });
    renderAt("/users/7");
    expect(await screen.findByText(/Map a Manager first/)).toBeInTheDocument();
    expect(screen.queryByLabelText("Client")).toBeNull();
  });

  test("backend rejection of a client is displayed", async () => {
    supDetail(mapped);
    clients.listClients.mockResolvedValue(list([client({ id: 20 })]));
    assign.assignSupervisorClient.mockRejectedValue({ status: 409, code: "client_not_under_manager", message: "This client does not belong to the Supervisor's Manager." });
    renderAt("/users/7");
    await userEvent.selectOptions(await screen.findByLabelText("Client"), "20");
    await userEvent.click(screen.getByRole("button", { name: "Assign client" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("does not belong");
  });

  test("changing Manager with a client asks to clear it, then retries with clear_client", async () => {
    supDetail({ ...mapped, client: { id: 5, client_name: "Acme", client_code: "A1" } });
    users.listUsers.mockResolvedValue(list([mgr(3, "Noah Mgr")]));
    assign.mapSupervisorManager
      .mockRejectedValueOnce({ status: 409, code: "has_client_assignment", message: "x", details: { client: { client_name: "Acme" } } })
      .mockResolvedValueOnce({});
    renderAt("/users/7");
    const sel = await screen.findByLabelText("Select new Manager");
    await waitFor(() => expect(within(sel).getByText(/Noah Mgr/)).toBeInTheDocument());
    await userEvent.selectOptions(sel, "3");
    await userEvent.click(screen.getByRole("button", { name: "Change Manager" }));
    await waitFor(() => expect(assign.mapSupervisorManager).toHaveBeenNthCalledWith(1, 7, 3, false));
    const dlg = await screen.findByRole("dialog");
    expect(dlg).toHaveTextContent("Acme");
    await userEvent.click(within(dlg).getByRole("button", { name: "Change Manager" }));
    await waitFor(() => expect(assign.mapSupervisorManager).toHaveBeenNthCalledWith(2, 7, 3, true));
  });

  test("assignment history is shown", async () => {
    supDetail(mapped);
    assign.getAssignments.mockResolvedValue({ assignments: {}, history: [{ id: 1, event_type: "supervisor_mapped", supervisor: "Sam Sup",
      manager: "Mia Mgr", client_code: null, actor: "Root", created_at: "2026-10-01T00:00:00Z" }] });
    renderAt("/users/7");
    expect(await screen.findByText("Supervisor mapped to Manager")).toBeInTheDocument();
  });
});
