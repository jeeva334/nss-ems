import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import App from "./App";

vi.mock("./services/healthService", () => ({
  getReadiness: () => Promise.resolve({ status: "ok", database: "up" }),
}));

test("renders shell navigation and dashboard", async () => {
  render(<MemoryRouter><App /></MemoryRouter>);
  expect(screen.getAllByText("User Management").length).toBeGreaterThan(0);
  expect(await screen.findByText(/API and database are reachable/)).toBeInTheDocument();
});
