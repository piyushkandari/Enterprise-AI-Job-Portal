// frontend/lib/auth.ts
import { api } from "./api";
import type { UserResponse } from "./types";

const TOKEN_KEY = "token";
const USER_KEY = "user";

export function saveAuth(token: string, user: UserResponse) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function getStoredUser(): UserResponse | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as UserResponse;
  } catch {
    return null;
  }
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function logout() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  window.location.href = "/login";
}

export async function login(email: string, password: string) {
  const { data } = await api.post("/auth/login", { email, password });
  // Fetch user info now that we have a token
  const token = data.access_token;
  localStorage.setItem(TOKEN_KEY, token);
  const meResp = await api.get<UserResponse>("/auth/me");
  saveAuth(token, meResp.data);
  return meResp.data;
}

export async function signup(
  email: string,
  password: string,
  role: "employer" | "candidate"
) {
  await api.post("/auth/signup", { email, password, role });
  return login(email, password);
}

/** Where to redirect a user after login, based on role */
export function dashboardPathFor(role: string): string {
  return role === "employer" ? "/employer/dashboard" : "/candidate/dashboard";
}