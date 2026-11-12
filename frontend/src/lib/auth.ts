const TOKEN_KEY = "clearbook_token";
const USER_KEY = "clearbook_user";

export interface AuthUser {
  user_id: string;
  email: string;
  full_name?: string;
  role: string;        // super_admin | ca_admin | ca_staff
  tenant_id?: string | null;
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
  document.cookie = `${TOKEN_KEY}=${token}; path=/; max-age=${60 * 60 * 24 * 7}; SameSite=Lax`;
}

export function setAuthUser(user: AuthUser): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function getAuthUser(): AuthUser | null {
  if (typeof window === "undefined") return null;
  try {
    const v = localStorage.getItem(USER_KEY);
    return v ? JSON.parse(v) : null;
  } catch { return null; }
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  document.cookie = `${TOKEN_KEY}=; path=/; max-age=0`;
}

export function isAuthenticated(): boolean {
  return !!getToken();
}

export function isSuperAdmin(): boolean {
  return getAuthUser()?.role === "super_admin";
}

export function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}