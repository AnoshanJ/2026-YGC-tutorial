import type { Customer } from "./users";

const STORAGE_KEY = "cs-user";

export function getCurrentUser(): Customer | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as Customer;
  } catch {
    return null;
  }
}

export function setCurrentUser(c: Customer) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(c));
}

export function clearCurrentUser() {
  localStorage.removeItem(STORAGE_KEY);
}

export function sessionKey(customerId: string): string {
  return `cs-session-${customerId}`;
}

export function getOrCreateSession(customerId: string): string {
  const key = sessionKey(customerId);
  let s = localStorage.getItem(key);
  if (!s) {
    s = `ui-${customerId.toLowerCase()}-${Date.now()}`;
    localStorage.setItem(key, s);
  }
  return s;
}

export function rotateSession(customerId: string): string {
  const key = sessionKey(customerId);
  const s = `ui-${customerId.toLowerCase()}-${Date.now()}`;
  localStorage.setItem(key, s);
  return s;
}
