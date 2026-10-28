import {
  apiFetch,
  clearToken,
  getCachedUser,
  getToken,
  isTokenExpired,
  readJson,
  setCachedUser,
  setToken
} from "./config.js?v=7";
import { applyTranslations, getLanguage, LANGUAGES, setLanguage, t } from "./i18n.js?v=7";
import { renderSidebar } from "./layout.js?v=7";
import { getErrorMessage, setButtonLoading, setCurrency, showToast } from "./ui.js?v=7";

const COMPANY_KEY = "companyLoaded";

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
  try {
    sessionStorage.removeItem(COMPANY_KEY);
  } catch {
    // Nothing cached.
  }
  window.location.href = "index.html";
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

// The business currency is needed by every page that shows money.
async function loadCompanySettings() {
  try {
    if (sessionStorage.getItem(COMPANY_KEY)) return;
  } catch {
    // Storage blocked: load every time.
  }

  const response = await apiFetch("/company");
  if (!response.ok) return;
  const company = await readJson(response);
  setCurrency(company.currency || "USD");
  try {
    sessionStorage.setItem(COMPANY_KEY, "1");
  } catch {
    // Fine: it will be loaded again on the next page.
  }
}

export function forgetCompanySettings() {
  try {
    sessionStorage.removeItem(COMPANY_KEY);
  } catch {
    // Nothing cached.
  }
}

// Elements marked with data-role="admin" are only shown to admins.
// This is a UX convenience; the API enforces the real permissions.
function applyRoleVisibility(user) {
  document.querySelectorAll("[data-role]").forEach((element) => {
    element.hidden = element.dataset.role !== user?.role;
  });
}

/**
 * Common setup for every protected page: auth check, sidebar, translations,
 * role-based visibility and business currency.
 * Returns the current user, or null when the visitor is being redirected.
 * With adminOnly, non-admins are sent to the dashboard.
 */
export async function initProtectedPage({ adminOnly = false } = {}) {
  if (!requireAuth()) return null;

  applyTranslations();

  const user = await loadCurrentUser();
  if (!user) {
    logout();
    return null;
  }

  if (adminOnly && !isAdmin(user)) {
    window.location.replace("dashboard.html");
    return null;
  }

  await loadCompanySettings();
  renderSidebar(user);
  document.querySelectorAll("[data-logout]").forEach((button) => button.addEventListener("click", logout));
  applyRoleVisibility(user);
  return user;
}

export function languageOptions(selected = getLanguage()) {
  return Object.entries(LANGUAGES)
    .map(([code, { label }]) => `<option value="${code}" ${code === selected ? "selected" : ""}>${label}</option>`)
    .join("");
}

export function initLoginPage() {
  applyTranslations();

  const languageSelect = document.getElementById("languageSelect");
  languageSelect.innerHTML = languageOptions();
  languageSelect.addEventListener("change", () => {
    setLanguage(languageSelect.value);
    applyTranslations();
  });

  const form = document.getElementById("loginForm");
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
    setButtonLoading(button, true, t("login.signingIn"));

    try {
      const response = await apiFetch("/auth/login", {
        method: "POST",
        body: JSON.stringify({ username, password })
      });

      const data = await readJson(response);

      if (!response.ok) {
        messageEl.textContent = getErrorMessage(data, t("login.failed"));
        messageEl.className = "form-message error";
        setButtonLoading(button, false);
        return;
      }

      clearToken();
      forgetCompanySettings();
      setToken(data.access_token);
      showToast(t("login.welcome"), "success");

      setTimeout(() => {
        window.location.href = "dashboard.html";
      }, 500);
    } catch (error) {
      console.error(error);
      messageEl.textContent = t("common.serverUnreachable");
      messageEl.className = "form-message error";
      setButtonLoading(button, false);
    }
  });
}
