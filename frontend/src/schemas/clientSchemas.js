import { z } from "zod";

const optional = (schema) => z.union([z.literal(""), schema]).optional();
const phone = z.string().trim().refine((v) => /^\+?[0-9]{7,15}$/.test(v.replace(/[\s\-()]/g, "")),
  "Enter a valid phone number (7-15 digits, optional leading +).");
const common = {
  client_name: z.string().trim().min(2, "Enter the client name.").max(200),
  address: optional(z.string().trim().max(500)),
  contact_name: optional(z.string().trim().max(150)),
  contact_email: optional(z.string().trim().email("Enter a valid email address.")),
  contact_phone: optional(phone),
};

export const createClientSchema = z.object({
  client_code: z.string().trim().regex(/^[A-Za-z0-9][A-Za-z0-9_-]{1,29}$/, "Use 2-30 letters, digits, hyphens or underscores (e.g. ACME-01)."),
  ...common,
});
export const editClientSchema = z.object(common);
