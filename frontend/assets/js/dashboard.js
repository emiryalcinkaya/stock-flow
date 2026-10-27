import { apiFetch, readJson } from "./config.js";
import { initProtectedPage } from "./auth.js";
import {
  escapeHtml,
  formatCurrency,
  formatDate,
  getErrorMessage,
  renderEmptyRow,
  showToast,
  statusBadge
} from "./ui.js";

const totalProductsEl = document.getElementById("totalProducts");
const lowStockCountEl = document.getElementById("lowStockCount");
const lowStockNoteEl = document.getElementById("lowStockNote");
const totalSalesEl = document.getElementById("totalSales");
const totalRevenueEl = document.getElementById("totalRevenue");
const recentSalesTable = document.getElementById("recentSalesTable");

async function loadDashboard() {
  try {
    const [summaryRes, salesRes] = await Promise.all([
      apiFetch("/dashboard/summary"),
      apiFetch("/sales/?limit=5")
    ]);

    const summary = await readJson(summaryRes);
    if (!summaryRes.ok) {
      showToast(getErrorMessage(summary, "Failed to load dashboard"), "error");
      return;
    }

    totalProductsEl.textContent = summary.total_products;
    lowStockCountEl.textContent = summary.low_stock;
    lowStockNoteEl.textContent = `Products with stock under ${summary.low_stock_threshold}`;
    totalSalesEl.textContent = summary.total_sales;
    totalRevenueEl.textContent = formatCurrency(summary.revenue);

    const sales = await readJson(salesRes);
    if (!salesRes.ok) {
      showToast(getErrorMessage(sales, "Failed to load sales"), "error");
      return;
    }

    renderRecentSales(sales);
  } catch (error) {
    console.error(error);
    showToast("Failed to load dashboard", "error");
  }
}

function renderRecentSales(sales) {
  if (!sales.length) {
    renderEmptyRow(recentSalesTable, 4, "No sales found yet.");
    return;
  }

  recentSalesTable.innerHTML = sales
    .map(
      (sale) => `
        <tr>
          <td>#${escapeHtml(sale.id)}</td>
          <td>${formatCurrency(sale.total_price)}</td>
          <td>${statusBadge(sale.status)}</td>
          <td>${escapeHtml(formatDate(sale.created_at))}</td>
        </tr>
      `
    )
    .join("");
}

if (await initProtectedPage()) {
  loadDashboard();
}
