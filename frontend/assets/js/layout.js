import { t } from "./i18n.js?v=9";
import { escapeHtml, refreshIcons } from "./ui.js?v=9";

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
      <button type="button" class="mobile-menu-toggle" aria-expanded="false"></button>
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
  initMobileMenu(sidebar.querySelector(".mobile-menu-toggle"));
  initTableLabels();
  initMobileCollapsibles();
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

// ----- Phones (see mobile.css; none of this shows on desktop) -----

const SMALL_SCREEN = window.matchMedia("(max-width: 860px)");

function initMobileMenu(button) {
  const root = document.documentElement;

  const render = () => {
    const open = root.classList.contains("nav-open");
    const label = t(open ? "nav.closeMenu" : "nav.menu");
    button.setAttribute("aria-label", label);
    button.setAttribute("aria-expanded", String(open));
    button.title = label;
    button.innerHTML = `<i data-lucide="${open ? "x" : "menu"}"></i>`;
    refreshIcons();
  };

  const setOpen = (open) => {
    root.classList.toggle("nav-open", open);
    render();
  };

  button.addEventListener("click", () => setOpen(!root.classList.contains("nav-open")));
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && root.classList.contains("nav-open")) setOpen(false);
  });
  // Rotating or resizing to desktop width must not leave the page locked.
  window.matchMedia("(min-width: 861px)").addEventListener("change", (e) => {
    if (e.matches) setOpen(false);
  });

  render();
}

// On phones each table row is shown as a card; every cell needs its column name.
function labelTable(table) {
  const headers = [...table.querySelectorAll("thead th")].map((th) => th.textContent.trim());
  if (!headers.length) return;

  for (const body of table.tBodies) {
    for (const row of body.rows) {
      let column = 0;
      for (const cell of row.cells) {
        if (cell.colSpan === 1 && cell.dataset.label !== headers[column]) {
          cell.dataset.label = headers[column] || "";
        }
        column += cell.colSpan;
      }
    }
  }
}

function initTableLabels() {
  let queued = false;
  const labelAll = () => {
    queued = false;
    document.querySelectorAll("table.table").forEach(labelTable);
  };

  // Rows are rendered by each page's script whenever data loads.
  new MutationObserver(() => {
    if (queued) return;
    queued = true;
    requestAnimationFrame(labelAll);
  }).observe(document.body, { childList: true, subtree: true });

  labelAll();
}

// Long forms such as "New product" start folded on phones so the list comes first.
function initMobileCollapsibles() {
  document.querySelectorAll("[data-mobile-collapse]").forEach((card) => {
    const header = card.querySelector(":scope > .card-header");
    if (!header) return;

    card.classList.add("mobile-collapsible", "is-folded");

    // Only a button on small screens; on desktop the header stays plain text.
    const syncRole = () => {
      if (SMALL_SCREEN.matches) {
        header.setAttribute("role", "button");
        header.tabIndex = 0;
      } else {
        header.removeAttribute("role");
        header.removeAttribute("tabindex");
      }
    };
    SMALL_SCREEN.addEventListener("change", syncRole);
    syncRole();

    const toggle = () => {
      if (!SMALL_SCREEN.matches) return;
      card.classList.toggle("is-folded");
    };
    header.addEventListener("click", toggle);
    header.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        toggle();
      }
    });
  });
}
