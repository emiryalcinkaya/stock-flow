// Override by defining window.STOCKFLOW_API_URL before the scripts load.
export const API_BASE_URL = window.STOCKFLOW_API_URL || "http://127.0.0.1:8000/api/v1";

const TOKEN_KEY = "token";
const USER_KEY = "currentUser";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(USER_KEY);
}

export function getCachedUser() {
  try {
    return JSON.parse(sessionStorage.getItem(USER_KEY));
  } catch {
    return null;
  }
}

export function setCachedUser(user) {
  sessionStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function isTokenExpired(token) {
  try {
    const payload = JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
    return !payload.exp || payload.exp * 1000 <= Date.now();
  } catch {
    return true;
  }
}

function isLoginPage() {
  const path = window.location.pathname;
  return path.endsWith("/index.html") || path.endsWith("/");
}

export async function apiFetch(endpoint, options = {}) {
  const token = getToken();

  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {})
  };

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers
  });

  if (response.status === 401 && !isLoginPage()) {
    clearToken();
    window.location.href = "index.html";
  }

  return response;
}

// Parses JSON without throwing on empty or non-JSON bodies.
export async function readJson(response) {
  try {
    return await response.json();
  } catch {
    return null;
  }
}
