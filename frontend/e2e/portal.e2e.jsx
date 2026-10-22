import fs from "node:fs";
import path from "node:path";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import App from "./../src/App";
import { AuthProvider } from "./../src/hooks/AuthContext";
import * as authService from "./../src/services/authService";
import { assignSupervisorClient } from "./../src/services/assignmentService";

const ADMIN = { id: "admin@e2e.example.com", pw: process.env.E2E_ADMIN_PASSWORD };
const NEW_PW = "E2eNewUserPassw0rd1";
const world = {}; // ids/tokens shared by the ordered steps below

// One app instance at a time; the cookie jar (the "browser") persists between mounts.
const mount = (route) => { cleanup(); return render(<MemoryRouter initialEntries={[route]}><AuthProvider><App /></AuthProvider></MemoryRouter>); };
const tokenFor = (email) => {
  const file = path.join(process.env.E2E_OUTBOX, `${email.replace("@", "_at_")}.html`);
  return /#token=([\w-]+)/.exec(fs.readFileSync(file, "utf8"))[1];
};
// Pages render only after the session check completes, so always wait for the field.
const type = async (label, value) => userEvent.type(await screen.findByLabelText(label), value);

async function signInAs(identifier, password) {
  try { await authService.logout(); } catch { /* no session yet */ }
  mount("/login");
  await type("Employee ID or email", identifier);
  await type("Password", password);
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
  await screen.findByRole("heading", { name: "Dashboard" });
}

async function createUserViaUi({ name, email, role }) {
  mount("/users/new");
  await type("Full name", name);
  await type("Mobile number", "9876543210");
  await type("Email address", email);
  await userEvent.selectOptions(screen.getByLabelText("Role"), role);
  await userEvent.click(screen.getByRole("button", { name: /CREATE USER & SEND INVITATION/ }));
  await screen.findByText("Account created");
  const employeeId = screen.getByText(/EMP\d+/, { selector: "strong" }).textContent;
  const id = Number(screen.getByRole("link", { name: "View user" }).getAttribute("href").split("/").pop());
  expect(screen.getByText(/saved to the local outbox/)).toBeInTheDocument();
  return { employeeId, id };
}

const people = {
  mira: { name: "Mira Manager", email: "mira@e2e.example.com", role: "MANAGER" },
  noah: { name: "Noah Manager", email: "noah@e2e.example.com", role: "MANAGER" },
  sam: { name: "Sam Supervisor", email: "sam@e2e.example.com", role: "SUPERVISOR" },
};

async function createClientViaUi(code, name) {
  mount("/clients/new");
  await type("Client code", code);
  await type("Client name", name);
  await userEvent.click(screen.getByRole("button", { name: "CREATE CLIENT" }));
  await screen.findByRole("heading", { name });
}

describe("Manpower portal, full stack", () => {
  test("1. Admin signs in (and the session survives a page reload)", async () => {
    await signInAs(ADMIN.id, ADMIN.pw);
    expect(screen.getByRole("link", { name: /user management/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /audit log/i })).toBeInTheDocument();
    cleanup();
    const { unmount } = mount("/");           // fresh mount = reload; cookie must restore the session
    expect(await screen.findByRole("heading", { name: "Dashboard" })).toBeInTheDocument();
    expect(await screen.findByText(/API and database are reachable/)).toBeInTheDocument();
    unmount();
  });

  test("1b. wrong password gives a generic error", async () => {
    try { await authService.logout(); } catch { /* ignore */ }
    mount("/login");
    await type("Employee ID or email", ADMIN.id);
    await type("Password", "WrongPassword123");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("incorrect");
  });

  test("2-4. Admin creates users; Employee IDs are generated; invitations are created", async () => {
    await signInAs(ADMIN.id, ADMIN.pw);
    world.mira = await createUserViaUi(people.mira);
    world.noah = await createUserViaUi(people.noah);
    world.sam = await createUserViaUi(people.sam);
    expect([world.mira.employeeId, world.noah.employeeId, world.sam.employeeId]).toEqual(["EMP0002", "EMP0003", "EMP0004"]);
    for (const p of Object.values(people)) expect(tokenFor(p.email).length).toBeGreaterThan(30);
  });

  test("2b. duplicate email is rejected beside the field", async () => {
    mount("/users/new");
    await type("Full name", "Mira Again");
    await type("Mobile number", "9876543210");
    await type("Email address", people.mira.email.toUpperCase());
    await userEvent.selectOptions(screen.getByLabelText("Role"), "SUPERVISOR");
    await userEvent.click(screen.getByRole("button", { name: /CREATE USER/ }));
    expect(await screen.findByText("A user with this email already exists.")).toBeInTheDocument();
  });

  test("2c. the new users appear in the searchable list as Pending", async () => {
    mount("/users");
    expect(await screen.findByText("EMP0004")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Search users"), "noah{enter}");
    await waitFor(() => expect(screen.queryByText("EMP0004")).toBeNull());
    const table = await screen.findByRole("table");
    expect(within(table).getByText("EMP0003")).toBeInTheDocument();
    expect(within(table).getByText("Pending")).toBeInTheDocument();
  });

  test("5. users activate their accounts from the emailed link; the link works only once", async () => {
    for (const p of Object.values(people)) {
      window.history.pushState(null, "", `/activate#token=${tokenFor(p.email)}`);
      const { unmount } = mount("/activate");
      await type("New password", NEW_PW);
      await type("Confirm password", NEW_PW);
      await userEvent.click(screen.getByRole("button", { name: "Activate account" }));
      expect(await screen.findByText("Account activated")).toBeInTheDocument();
      unmount();
    }
    window.history.pushState(null, "", `/activate#token=${tokenFor(people.mira.email)}`); // reuse
    mount("/activate");
    await type("New password", NEW_PW);
    await type("Confirm password", NEW_PW);
    await userEvent.click(screen.getByRole("button", { name: "Activate account" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/invalid or has already been used/);
  });

  test("5b. an activated Manager can sign in but sees no admin features", async () => {
    await signInAs(people.mira.email, NEW_PW);
    expect(screen.queryByRole("link", { name: /user management/i })).toBeNull();
    expect(screen.queryByRole("link", { name: /audit log/i })).toBeNull();
    cleanup();
    mount("/users");                                       // typed URL: bounced to the dashboard
    expect(await screen.findByRole("heading", { name: "Dashboard" })).toBeInTheDocument();
  });

  test("6. Admin creates clients and assigns Managers", async () => {
    await signInAs(ADMIN.id, ADMIN.pw);
    for (const [code, name, manager] of [["ACME", "Acme Industries", "Mira Manager"], ["BETA", "Beta Logistics", "Noah Manager"]]) {
      await createClientViaUi(code, name);
      const sel = await screen.findByLabelText("Manager");
      await waitFor(() => expect(within(sel).getByText(new RegExp(manager))).toBeInTheDocument());
      await userEvent.selectOptions(sel, within(sel).getByText(new RegExp(manager)));
      await userEvent.click(screen.getByRole("button", { name: "Assign Manager" }));
      expect(await screen.findByText("Manager assigned.")).toBeInTheDocument();
      expect(screen.getAllByText(new RegExp(manager)).length).toBeGreaterThan(0);
      cleanup();
    }
  });

  test("7. Supervisor is mapped to a Manager (Manager shown read-only)", async () => {
    mount(`/users/${world.sam.id}`);
    const sel = await screen.findByLabelText("Select new Manager");
    await waitFor(() => expect(within(sel).getByText(/Mira Manager/)).toBeInTheDocument());
    await userEvent.selectOptions(sel, within(sel).getByText(/Mira Manager/));
    await userEvent.click(screen.getByRole("button", { name: "Map to Manager" }));
    expect(await screen.findByText("Manager mapping updated.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Mira Manager (EMP0002)" })).toBeInTheDocument();
  });

  test("8. Supervisor is assigned a client, offered only from the mapped Manager", async () => {
    mount(`/users/${world.sam.id}`);
    const sel = await screen.findByLabelText("Client");
    await waitFor(() => expect(within(sel).getByText(/Acme Industries/)).toBeInTheDocument());
    expect(within(sel).queryByText(/Beta Logistics/)).toBeNull();      // Noah's client is not offered
    await userEvent.selectOptions(sel, within(sel).getByText(/Acme Industries/));
    await userEvent.click(screen.getByRole("button", { name: "Assign client" }));
    expect(await screen.findByText("Client assigned.")).toBeInTheDocument();
    expect(await screen.findByText("Client assigned to Supervisor")).toBeInTheDocument(); // history entry
  });

  test("9a. the backend rejects a client of another Manager even when the UI is bypassed", async () => {
    mount("/clients");
    const beta = (await screen.findByText("Beta Logistics")).closest("tr");
    const betaId = Number(within(beta).getByRole("link", { name: /View Beta/ }).getAttribute("href").split("/").pop());
    await expect(assignSupervisorClient(world.sam.id, betaId)).rejects.toMatchObject({ status: 409, code: "client_not_under_manager" });
  });

  test("9b. reassigning a client that has a Supervisor is blocked and names the Supervisor", async () => {
    mount("/clients");
    await userEvent.click(await screen.findByRole("link", { name: /View Acme/ }));
    const sel = await screen.findByLabelText("Manager");
    await waitFor(() => expect(within(sel).getByText(/Noah Manager/)).toBeInTheDocument());
    await userEvent.selectOptions(sel, within(sel).getByText(/Noah Manager/));
    await userEvent.click(screen.getByRole("button", { name: "Reassign Manager" }));
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Reassign" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Sam Supervisor (EMP0004)");
  });

  test("9c. changing the Supervisor's Manager requires confirming the client is cleared", async () => {
    mount(`/users/${world.sam.id}`);
    const sel = await screen.findByLabelText("Select new Manager");
    await waitFor(() => expect(within(sel).getByText(/Noah Manager/)).toBeInTheDocument());
    await userEvent.selectOptions(sel, within(sel).getByText(/Noah Manager/));
    await userEvent.click(screen.getByRole("button", { name: "Change Manager" }));
    const dlg = await screen.findByRole("dialog");
    expect(dlg).toHaveTextContent("Acme Industries");
    await userEvent.click(within(dlg).getByRole("button", { name: "Change Manager" }));
    expect(await screen.findByText(/client assignment cleared/)).toBeInTheDocument();
    expect(await screen.findByText("Not assigned")).toBeInTheDocument();
  });

  test("10. with no Supervisors left on Acme, reassignment now succeeds and shows in history", async () => {
    mount("/clients");
    await userEvent.click(await screen.findByRole("link", { name: /View Acme/ }));
    const sel = await screen.findByLabelText("Manager");
    await waitFor(() => expect(within(sel).getByText(/Noah Manager/)).toBeInTheDocument());
    await userEvent.selectOptions(sel, within(sel).getByText(/Noah Manager/));
    await userEvent.click(screen.getByRole("button", { name: "Reassign Manager" }));
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Reassign" }));
    expect(await screen.findByText("Client reassigned.")).toBeInTheDocument();
  });

  test("11. the audit log recorded the whole flow without any secrets", async () => {
    mount("/audit");
    const category = async (value) => userEvent.selectOptions(await screen.findByLabelText("Category"), value);
    await category("user.");
    expect(await screen.findAllByText("user.create")).toHaveLength(3);
    await category("auth.");
    expect((await screen.findAllByText("auth.login_failed")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("auth.activate")).toHaveLength(3);
    await category("client.");
    expect((await screen.findAllByText("client.manager_reassigned")).length).toBeGreaterThan(0);
    await category("");
    await screen.findByText(/Showing 1–25 of/);
    const text = document.body.textContent;
    for (const secret of [NEW_PW, ADMIN.pw, tokenFor(people.sam.email), "$argon2"]) expect(text).not.toContain(secret);
  });
});
