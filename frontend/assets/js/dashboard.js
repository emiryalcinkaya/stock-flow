import { apiFetch, readJson } from "./config.js?v=7";
import { initProtectedPage } from "./auth.js?v=7";
import { t } from "./i18n.js?v=7";
import { formatQuantity, reasonLabel } from "./inventory.js?v=7";
import {
  escapeHtml,
  formatCurrency,
  formatDate,
  getErrorMessage,
  renderEmptyRow,
  showToast,
  statusBadge
} from "./ui.js?v=7";

const totalProductsEl = document.getElementById("totalProducts");
const lowStockCountEl = document.getElementById("lowStockCount");
const lowStockNoteEl = document.getElementById("lowStockNote");
const stockValueEl = document.getElementById("stockValue");
const totalRevenueEl = document.getElementById("totalRevenue");
const salesNoteEl = document.getElementById("salesNote");
const lowStockTable = document.getElementById("lowStockTable");
const recentSalesTable = document.getElementById("recentSalesTable");
const companyLogoEl = document.getElementById("companyLogo");
const companyNameEl = document.getElementById("companyName");
const companyDescriptionEl = document.getElementById("companyDescription");

// The welcome card shows the business using Eysto; Eysto's own branding is the fallback.
async function loadCompany() {
  const response = await apiFetch("/company");
  if (!response.ok) return;

  const company = await readJson(response);
  if (company.name) companyNameEl.textContent = company.name;
  if (company.description) companyDescriptionEl.textContent = company.description;
  if (company.logo) companyLogoEl.src = company.logo;
  companyLogoEl.alt = company.name ? `${company.name} logo` : "";
}

async function loadDashboard() {
  try {
    const [summaryRes, lowStockRes, salesRes] = await Promise.all([
      apiFetch("/dashboard/summary"),
      apiFetch("/products/?low_stock=true&sort=low_stock_first&limit=10"),
      apiFetch("/sales/?limit=5")
    ]);

    const summary = await readJson(summaryRes);
    if (!summaryRes.ok) {
      showToast(getErrorMessage(summary, t("dashboard.loadFailed")), "error");
      return;
    }

    totalProductsEl.textContent = summary.total_products;
    lowStockCountEl.textContent = summary.low_stock;
    lowStockNoteEl.textContent = t("dashboard.lowStockNote", { threshold: summary.low_stock_threshold });
    stockValueEl.textContent = formatCurrency(summary.stock_value);
    totalRevenueEl.textContent = formatCurrency(summary.revenue);
    salesNoteEl.textContent = t("dashboard.salesNote", { count: summary.total_sales });

    const lowStock = await readJson(lowStockRes);
    if (lowStockRes.ok) renderLowStock(lowStock);

    const sales = await readJson(salesRes);
    if (!salesRes.ok) {
      showToast(getErrorMessage(sales, t("dashboard.loadFailed")), "error");
      return;
    }

    renderRecentSales(sales);
  } catch (error) {
    console.error(error);
    showToast(t("dashboard.loadFailed"), "error");
  }
}

function renderLowStock(products) {
  if (!products.length) {
    renderEmptyRow(lowStockTable, 4, t("dashboard.noLowStock"));
    return;
  }

  lowStockTable.innerHTML = products
    .map(
      (product) => `
        <tr>
          <td><strong>${escapeHtml(product.name)}</strong></td>
          <td>${escapeHtml(product.category_name || "-")}</td>
          <td class="stock-low">${escapeHtml(formatQuantity(product.stock_quantity, product.unit))}</td>
          <td>${
            product.min_stock === null
              ? escapeHtml(t("common.default"))
              : escapeHtml(formatQuantity(product.min_stock, product.unit))
          }</td>
        </tr>
      `
    )
    .join("");
}

function renderRecentSales(sales) {
  if (!sales.length) {
    renderEmptyRow(recentSalesTable, 5, t("dashboard.noStockOuts"));
    return;
  }

  recentSalesTable.innerHTML = sales
    .map(
      (sale) => `
        <tr>
          <td>#${escapeHtml(sale.id)}</td>
          <td>${escapeHtml(reasonLabel(sale.reason))}</td>
          <td>${formatCurrency(sale.total_price)}</td>
          <td>${statusBadge(sale.status)}</td>
          <td>${escapeHtml(formatDate(sale.created_at))}</td>
        </tr>
      `
    )
    .join("");
}

if (await initProtectedPage()) {
  loadCompany().catch((error) => console.error(error));
  loadDashboard();
}
