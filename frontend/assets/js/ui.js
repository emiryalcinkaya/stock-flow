import { apiFetch } from "./config.js?v=9";
import { getLocale, t, translateApiError } from "./i18n.js?v=9";

const HTML_ESCAPES = {
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;"
};

// Every value coming from the API must go through this before it is put into innerHTML.
export function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => HTML_ESCAPES[char]);
}

export function showToast(message, type = "info") {
  const oldToast = document.querySelector(".toast");
  if (oldToast) oldToast.remove();

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.setAttribute("role", type === "error" ? "alert" : "status");
  toast.textContent = message;

  document.body.appendChild(toast);

  setTimeout(() => {
    toast.classList.add("toast-show");
  }, 10);

  setTimeout(() => {
    toast.classList.remove("toast-show");
    setTimeout(() => toast.remove(), 300);
  }, 2800);
}

// ----- Money, numbers and dates ------------------------------------------

const CURRENCY_KEY = "currency";
export const CURRENCIES = ["TRY", "USD", "EUR"];

// The business currency comes from the company profile and is cached per session.
export function getCurrency() {
  try {
    return sessionStorage.getItem(CURRENCY_KEY) || "USD";
  } catch {
    return "USD";
  }
}

export function setCurrency(code) {
  try {
    sessionStorage.setItem(CURRENCY_KEY, code);
  } catch {
    // Not critical: amounts fall back to USD formatting.
  }
}

export function formatCurrency(value) {
  return new Intl.NumberFormat(getLocale(), { style: "currency", currency: getCurrency() }).format(
    Number(value || 0)
  );
}

export function formatNumber(value) {
  return new Intl.NumberFormat(getLocale(), { maximumFractionDigits: 3 }).format(Number(value || 0));
}

export function formatDate(dateString) {
  if (!dateString) return "-";
  return new Date(dateString).toLocaleString(getLocale(), { dateStyle: "medium", timeStyle: "short" });
}

export function formatDay(dateString) {
  if (!dateString) return "-";
  return new Date(dateString).toLocaleDateString(getLocale(), { dateStyle: "medium" });
}

export function formatMonth(yearMonth) {
  const [year, month] = yearMonth.split("-").map(Number);
  return new Date(year, month - 1, 1).toLocaleDateString(getLocale(), { month: "short", year: "numeric" });
}

// ----- Errors and empty states -----------------------------------------

// FastAPI returns `detail` as a string, or as a list of validation errors.
export function getErrorMessage(data, fallback) {
  if (!data || !data.detail) return fallback;
  if (typeof data.detail === "string") return translateApiError(data.detail);
  if (Array.isArray(data.detail) && data.detail.length) {
    const first = data.detail[0];
    const field = Array.isArray(first.loc) ? first.loc[first.loc.length - 1] : "";
    const message = String(first.msg || "").replace(/^Value error, /, "");
    return field ? `${field}: ${message}` : message;
  }
  return fallback;
}

export function renderEmptyState(container, message) {
  container.innerHTML = `<div class="empty-state">${escapeHtml(message)}</div>`;
}

// Keeps the table in the DOM, so it can be filled again later without a reload.
export function renderEmptyRow(tbody, colspan, message) {
  tbody.innerHTML = `
    <tr class="empty-row">
      <td colspan="${colspan}"><div class="empty-state">${escapeHtml(message)}</div></td>
    </tr>
  `;
}

export function refreshIcons() {
  if (window.lucide) {
    window.lucide.createIcons();
  }
}

export function setButtonLoading(button, isLoading, loadingText = t("common.loading")) {
  if (!button) return;

  if (isLoading) {
    if (!button.disabled) {
      button.dataset.originalHtml = button.innerHTML;
    }
    button.textContent = loadingText;
    button.disabled = true;
  } else {
    if (button.dataset.originalHtml) {
      button.innerHTML = button.dataset.originalHtml;
    }
    button.disabled = false;
    refreshIcons();
  }
}

export function statusBadge(status) {
  const safe = escapeHtml(status);
  return `<span class="status-badge status-${safe}">${escapeHtml(t(`status.${status}`))}</span>`;
}

// ----- Paging ------------------------------------------------------------

export const PAGE_SIZE = 50;

export function totalCount(response) {
  return Number(response.headers.get("X-Total-Count") || 0);
}

/**
 * Renders "1–50 of 230" with previous/next buttons into `container`.
 * `onPage(newSkip)` is called when the user changes page.
 */
export function renderPagination(container, { total, skip, limit = PAGE_SIZE, onPage }) {
  if (!container) return;
  if (total <= limit && skip === 0) {
    container.innerHTML = "";
    return;
  }

  const from = total === 0 ? 0 : skip + 1;
  const to = Math.min(skip + limit, total);
  container.innerHTML = `
    <div class="pagination">
      <span class="pagination-range">${escapeHtml(t("pager.range", { from, to, total }))}</span>
      <button class="btn btn-secondary icon-btn" type="button" data-page-step="-1" ${skip === 0 ? "disabled" : ""}
        aria-label="${escapeHtml(t("pager.previous"))}">
        <i data-lucide="chevron-left"></i>
      </button>
      <button class="btn btn-secondary icon-btn" type="button" data-page-step="1" ${to >= total ? "disabled" : ""}
        aria-label="${escapeHtml(t("pager.next"))}">
        <i data-lucide="chevron-right"></i>
      </button>
    </div>
  `;
  container.onclick = (e) => {
    const button = e.target.closest("[data-page-step]");
    if (!button || button.disabled) return;
    onPage(Math.max(0, skip + Number(button.dataset.pageStep) * limit));
  };
  refreshIcons();
}

// ----- Downloads ---------------------------------------------------------

// Downloads need the auth header, so a plain link won't do.
export async function downloadFile(endpoint, filename) {
  const response = await apiFetch(endpoint);
  if (!response.ok) {
    showToast(t("common.downloadFailed"), "error");
    return;
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
