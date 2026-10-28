import { t } from "./i18n.js?v=7";
import { escapeHtml, refreshIcons } from "./ui.js?v=7";

// The sidebar is built here once instead of being copied into every page.

const NAV_ITEMS = [
  { page: "dashboard", href: "dashboard.html", icon: "layout-dashboard", label: "nav.dashboard" },
  { page: "products", href: "products.html", icon: "package", label: "nav.products" },
  { page: "stock-out", href: "sales.html", icon: "package-minus", label: "nav.stockOut" },
  { page: "stock-out-history", href: "sales-history.html", icon: "history", label: "nav.stockOutHistory" },
  { page: "stock-counts", href: "stock-counts.html", icon: "clipboard-check", label: "nav.stockCounts" },
  { page: "reports", href: "reports.html", icon: "chart-column", label: "nav.reports" },
  { page: "settings", href: "settings.html", icon: "settings", label: "nav.settings", admin: true }
];

const SIDEBAR_KEY = "sidebarCollapsed";

export function renderSidebar(user) {
  const sidebar = document.querySelector(".sidebar");
  if (!sidebar) return;

  const current = document.body.dataset.page;
  const isAdmin = user?.role === "admin";

  const links = NAV_ITEMS.filter((item) => !item.admin || isAdmin)
    .map(
      (item) => `
        <a class="nav-link ${item.page === current ? "active" : ""}" href="${item.href}" title="${escapeHtml(t(item.label))}">
          <i data-lucide="${item.icon}"></i>
          <span>${escapeHtml(t(item.label))}</span>
        </a>
      `
    )
    .join("");

  sidebar.innerHTML = `
    <div class="brand">
      <img src="assets/images/logo.svg" alt="" class="brand-logo" />
      <div>
        <div class="brand-title">Eysto</div>
      </div>
      <button type="button" class="sidebar-toggle"></button>
    </div>

    <nav class="nav">${links}</nav>

    <div class="sidebar-footer">
      <a class="sidebar-user ${current === "account" ? "active" : ""}" href="account.html" title="${escapeHtml(t("nav.account"))}">
        <div class="sidebar-user-name">${escapeHtml(user?.full_name || "")}</div>
        <div class="sidebar-user-role">${escapeHtml(t(`role.${user?.role}`))}</div>
      </a>
      <button class="btn btn-secondary logout-btn" data-logout title="${escapeHtml(t("nav.logout"))}">
        <i data-lucide="log-out"></i>
        <span>${escapeHtml(t("nav.logout"))}</span>
      </button>
    </div>
  `;

  initSidebarToggle(sidebar.querySelector(".sidebar-toggle"));
  refreshIcons();
}

// Each page's <head> applies the saved state before render, so there is no flash.
function initSidebarToggle(button) {
  const render = () => {
    const collapsed = document.documentElement.classList.contains("sidebar-collapsed");
    const label = t(collapsed ? "nav.expand" : "nav.collapse");
    button.setAttribute("aria-label", label);
    button.title = label;
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
