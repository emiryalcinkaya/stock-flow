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
  }, 2500);
}

const currencyFormatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD"
});

export function formatCurrency(value) {
  return currencyFormatter.format(Number(value || 0));
}

export function formatDate(dateString) {
  if (!dateString) return "-";
  return new Date(dateString).toLocaleString();
}

// FastAPI returns `detail` as a string, or as a list of validation errors.
export function getErrorMessage(data, fallback) {
  if (!data || !data.detail) return fallback;
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.detail) && data.detail.length) {
    const first = data.detail[0];
    const field = Array.isArray(first.loc) ? first.loc[first.loc.length - 1] : "";
    return field ? `${field}: ${first.msg}` : first.msg;
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

export function setButtonLoading(button, isLoading, loadingText = "Loading...") {
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
  return `<span class="status-badge status-${safe}">${safe}</span>`;
}
