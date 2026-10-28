import {
  apiFetch,
  clearToken,
  getCachedUser,
  getToken,
  isTokenExpired,
  readJson,
  setCachedUser,
  setToken
} from "./config.js?v=5";
import { getErrorMessage, refreshIcons, setButtonLoading, showToast } from "./ui.js?v=5";

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

const SIDEBAR_KEY = "sidebarCollapsed";

// Each page's <head> applies the saved state before render, so there is no flash.
function initSidebarToggle() {
  const brand = document.querySelector(".sidebar .brand");
  if (!brand) return;

  // Collapsed sidebar shows icons only, so give every item a hover label.
  document.querySelectorAll(".sidebar .nav-link, .sidebar [data-logout]").forEach((item) => {
    item.title = item.textContent.trim();
  });

  const button = document.createElement("button");
  button.type = "button";
  button.className = "sidebar-toggle";
  brand.appendChild(button);

  const render = () => {
    const collapsed = document.documentElement.classList.contains("sidebar-collapsed");
    button.setAttribute("aria-label", collapsed ? "Expand sidebar" : "Collapse sidebar");
    button.title = button.getAttribute("aria-label");
    button.innerHTML = `<i data-lucide="${collapsed ? "panel-left-open" : "panel-left-close"}"></i>`;
    refreshIcons();
  };

  button.addEventListener("click", () => {
    const collapsed = document.documentElement.classList.toggle("sidebar-collapsed");
    try {
      localStorage.setItem(SIDEBAR_KEY, collapsed ? "1" : "0");
    } catch {
      // Storage can be unavailable (private mode); the toggle still works for this page.
    }
    render();
  });

  render();
}

/**
 * Common setup for every protected page.
 * Returns the current user, or null when the visitor is being redirected.
 */
export async function initProtectedPage() {
  if (!requireAuth()) return null;

  initSidebarLogout();
  initSidebarToggle();

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
