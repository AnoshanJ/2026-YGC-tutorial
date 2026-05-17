// Hardcoded customer directory for the mock login. Mirrors
// agents/cs-agent/data/customers.json so the email entered at login resolves
// to the same customer the agent loads server-side from context.customer_id.
// Password is never validated.

export type Customer = {
  id: string;
  email: string;
  name: string;
  tier: "bronze" | "silver" | "gold" | "platinum";
  region: "NA" | "EMEA" | "APAC";
};

export const USERS: Record<string, Customer> = {
  "ava.morgan@example.com": {
    id: "C-1001",
    email: "ava.morgan@example.com",
    name: "Ava Morgan",
    tier: "gold",
    region: "NA",
  },
  "lukas.weber@example.de": {
    id: "C-1002",
    email: "lukas.weber@example.de",
    name: "Lukas Weber",
    tier: "silver",
    region: "EMEA",
  },
  "sora.tanaka@example.jp": {
    id: "C-1003",
    email: "sora.tanaka@example.jp",
    name: "Sora Tanaka",
    tier: "gold",
    region: "APAC",
  },
  "diego.alvarez@example.com": {
    id: "C-1004",
    email: "diego.alvarez@example.com",
    name: "Diego Alvarez",
    tier: "bronze",
    region: "NA",
  },
  "marie.dubois@example.fr": {
    id: "C-1005",
    email: "marie.dubois@example.fr",
    name: "Marie Dubois",
    tier: "platinum",
    region: "EMEA",
  },
  "kai.hayashi@example.jp": {
    id: "C-1006",
    email: "kai.hayashi@example.jp",
    name: "Kai Hayashi",
    tier: "silver",
    region: "APAC",
  },
  "olivia.smith@example.com": {
    id: "C-1007",
    email: "olivia.smith@example.com",
    name: "Olivia Smith",
    tier: "gold",
    region: "NA",
  },
  "hans.muller@example.de": {
    id: "C-1008",
    email: "hans.muller@example.de",
    name: "Hans Muller",
    tier: "bronze",
    region: "EMEA",
  },
  "priya.nair@example.in": {
    id: "C-1009",
    email: "priya.nair@example.in",
    name: "Priya Nair",
    tier: "silver",
    region: "APAC",
  },
  "noah.brown@example.com": {
    id: "C-1010",
    email: "noah.brown@example.com",
    name: "Noah Brown",
    tier: "platinum",
    region: "NA",
  },
};

export function findUser(email: string): Customer | null {
  return USERS[email.trim().toLowerCase()] ?? null;
}
