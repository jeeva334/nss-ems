import { z } from "zod";

const mobile = z.string().trim().refine((v) => /^\+?[0-9]{7,15}$/.test(v.replace(/[\s\-()]/g, "")),
  "Enter a valid mobile number (7-15 digits, optional leading +).");
const name = z.string().trim().min(2, "Enter the full name.").max(150);
const email = z.string().trim().min(1, "Enter an email address.").email("Enter a valid email address.");

export const createUserSchema = z.object({
  full_name: name,
  mobile_number: mobile,
  email,
  role: z.enum(["ADMIN", "MANAGER", "SUPERVISOR"], { errorMap: () => ({ message: "Select a role." }) }),
});

export const editUserSchema = z.object({ full_name: name, mobile_number: mobile, email });

// Mirrors the backend policy; the backend remains authoritative.
export const activateSchema = z.object({
  password: z.string().min(12, "Use at least 12 characters.").max(128, "Use at most 128 characters.")
    .refine((v) => /[A-Za-z]/.test(v) && /\d/.test(v), "Include both letters and digits."),
  confirm_password: z.string(),
}).refine((d) => d.password === d.confirm_password, { path: ["confirm_password"], message: "Passwords do not match." });
