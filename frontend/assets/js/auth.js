import {
  apiFetch,
  clearToken,
  getCachedUser,
  getToken,
  isTokenExpired,
  readJson,
  setCachedUser,
  setToken
} from "./config.js";
import { getErrorMessage, setButtonLoading, showToast } from "./ui.js";

export function requireAuth() {
  const token = getToken();
  if (!token || isTokenExpired(token)) {
    clearToken();
    window.location.replace("index.html");
    return false;
  }
  return true;
}

export function logout() {
  clearToken();
  window.location.href = "index.html";
}

export function initSidebarLogout() {
  const logoutButtons = document.querySelectorAll("[data-logout]");
  logoutButtons.forEach((button) => {
    button.addEventListener("click", logout);
  });
}

export function isAdmin(user) {
  return user?.role === "admin";
}

export async function loadCurrentUser() {
  const cached = getCachedUser();
  if (cached) return cached;

  const response = await apiFetch("/auth/me");
  if (!response.ok) return null;

  const user = await readJson(response);
  setCachedUser(user);
  return user;
}

// Elements marked with data-role="admin" are only shown to admins.
// This is a UX convenience; the API enforces the real permissions.
function applyRoleVisibility(user) {
  document.querySelectorAll("[data-role]").forEach((element) => {
    element.hidden = element.dataset.role !== user?.role;
  });
}

function renderSidebarUser(user) {
  const container = document.querySelector("[data-current-user]");
  if (!container || !user) return;

  container.querySelector("[data-user-name]").textContent = user.full_name;
  container.querySelector("[data-user-role]").textContent = user.role;
  container.hidden = false;
}

/**
 * Common setup for every protected page.
 * Returns the current user, or null when the visitor is being redirected.
 */
export async function initProtectedPage() {
  if (!requireAuth()) return null;

  initSidebarLogout();

  const user = await loadCurrentUser();
  if (!user) {
    logout();
    return null;
  }

  applyRoleVisibility(user);
  renderSidebarUser(user);
  return user;
}

export function initLoginPage() {
  const form = document.getElementById("loginForm");
  if (!form) return;

  const token = getToken();
  if (token && !isTokenExpired(token)) {
    window.location.replace("dashboard.html");
    return;
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const username = document.getElementById("username").value.trim();
    // Passwords are sent as typed: spaces can be part of a password.
    const password = document.getElementById("password").value;
    const messageEl = document.getElementById("message");
    const button = document.getElementById("loginButton");

    messageEl.textContent = "";
    messageEl.className = "form-message";
    setButtonLoading(button, true, "Signing in...");

    try {
      const response = await apiFetch("/auth/login", {
        method: "POST",
        body: JSON.stringify({ username, password })
      });

      const data = await readJson(response);

      if (!response.ok) {
        messageEl.textContent = getErrorMessage(data, "Login failed");
        messageEl.className = "form-message error";
        setButtonLoading(button, false);
        return;
      }

      clearToken();
      setToken(data.access_token);
      messageEl.textContent = "Login successful!";
      messageEl.className = "form-message success";
      showToast("Welcome back", "success");

      setTimeout(() => {
        window.location.href = "dashboard.html";
      }, 700);
    } catch (error) {
      console.error(error);
      messageEl.textContent = "Could not reach the server";
      messageEl.className = "form-message error";
      setButtonLoading(button, false);
    }
  });
}
