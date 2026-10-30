import { apiFetch, readJson } from "./config.js?v=9";
import { initProtectedPage } from "./auth.js?v=9";
import { csvDelimiter, t } from "./i18n.js?v=9";
import { formatQuantity } from "./inventory.js?v=9";
import {
  downloadFile,
  escapeHtml,
  formatCurrency,
  formatDay,
  formatMonth,
  getErrorMessage,
  renderEmptyRow,
  showToast
} from "./ui.js?v=9";

const $ = (id) => document.getElementById(id);

const isoDate = (date) =>
  `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;

function periodParams() {
  const params = new URLSearchParams();
  if ($("dateFrom").value) params.set("date_from", $("dateFrom").value);
  if ($("dateTo").value) params.set("date_to", $("dateTo").value);
  return params;
}

async function loadReport() {
  const response = await apiFetch(`/reports/overview?${periodParams()}`);
  const report = await readJson(response);
  if (!response.ok) {
    showToast(getErrorMessage(report, t("reports.loadFailed")), "error");
    return;
  }

  // Show the period the server actually used (it fills in defaults).
  $("dateFrom").value = report.period.date_from;
  $("dateTo").value = report.period.date_to;

  renderTotals(report.totals);
  renderMonthly(report.monthly);
  renderTopProducts(report.top_products);
  renderSlowMovers(report.slow_movers, report.slow_days);
  renderWarehouses(report.warehouses);
  renderSuppliers(report.suppliers);
}

function renderTotals(totals) {
  $("stockInValue").textContent = formatCurrency(totals.stock_in_value);
  $("stockInNote").textContent = t("reports.stockInNote", { count: totals.stock_ins });
  $("stockOutValue").textContent = formatCurrency(totals.stock_out_value);
  $("stockOutNote").textContent = t("reports.stockOutNote", { count: totals.stock_outs });
  $("revenueValue").textContent = formatCurrency(totals.sales_revenue);
  $("profitValue").textContent = formatCurrency(totals.gross_profit);
  $("profitNote").textContent =
    totals.profit_coverage < 1
      ? t("reports.profitPartial", { percent: Math.round(totals.profit_coverage * 100) })
      : t("reports.profitNote");
}

function renderMonthly(months) {
  const max = Math.max(1, ...months.flatMap((m) => [m.stock_in_value, m.stock_out_value]));

  $("monthlyChart").innerHTML = months
    .map(
      (m) => `
        <div class="bar-group" title="${escapeHtml(formatMonth(m.month))}">
          <div class="bars">
            <div class="bar bar-in" style="height:${(m.stock_in_value / max) * 100}%"
              title="${escapeHtml(t("reports.stockInValue"))}: ${escapeHtml(formatCurrency(m.stock_in_value))}"></div>
            <div class="bar bar-out" style="height:${(m.stock_out_value / max) * 100}%"
              title="${escapeHtml(t("reports.stockOutValue"))}: ${escapeHtml(formatCurrency(m.stock_out_value))}"></div>
          </div>
          <div class="bar-label">${escapeHtml(formatMonth(m.month))}</div>
        </div>
      `
    )
    .join("");

  $("monthlyTable").innerHTML = months
    .map(
      (m) => `
        <tr>
          <td>${escapeHtml(formatMonth(m.month))}</td>
          <td>${escapeHtml(m.stock_ins)}</td>
          <td>${formatCurrency(m.stock_in_value)}</td>
          <td>${escapeHtml(m.stock_outs)}</td>
          <td>${formatCurrency(m.stock_out_value)}</td>
          <td>${formatCurrency(m.sales_revenue)}</td>
        </tr>
      `
    )
    .join("");
}

function renderTopProducts(products) {
  if (!products.length) {
    renderEmptyRow($("topProductsTable"), 3, t("reports.noData"));
    return;
  }
  $("topProductsTable").innerHTML = products
    .map(
      (p) => `
        <tr>
          <td><strong>${escapeHtml(p.name)}</strong></td>
          <td>${escapeHtml(formatQuantity(p.quantity, p.unit))}</td>
          <td>${formatCurrency(p.value)}</td>
        </tr>
      `
    )
    .join("");
}

function renderSlowMovers(products, days) {
  $("slowTitle").textContent = t("reports.slowMovers", { days });
  if (!products.length) {
    renderEmptyRow($("slowTable"), 3, t("reports.noSlowMovers"));
    return;
  }
  $("slowTable").innerHTML = products
    .map(
      (p) => `
        <tr>
          <td><strong>${escapeHtml(p.name)}</strong></td>
          <td>${escapeHtml(formatQuantity(p.stock_quantity, p.unit))}${
            p.value === null ? "" : ` <span class="metric-note">(${formatCurrency(p.value)})</span>`
          }</td>
          <td>${escapeHtml(p.last_out_at ? formatDay(p.last_out_at) : t("reports.never"))}</td>
        </tr>
      `
    )
    .join("");
}

function renderWarehouses(warehouses) {
  $("warehouseTable").innerHTML = warehouses
    .map(
      (w) => `
        <tr>
          <td><strong>${escapeHtml(w.name)}</strong></td>
          <td>${escapeHtml(w.products)}</td>
          <td>${formatCurrency(w.value)}</td>
          <td>${formatCurrency(w.cost_value)}</td>
        </tr>
      `
    )
    .join("");
}

function renderSuppliers(suppliers) {
  if (!suppliers.length) {
    renderEmptyRow($("supplierTable"), 3, t("reports.noPurchases"));
    return;
  }
  $("supplierTable").innerHTML = suppliers
    .map(
      (s) => `
        <tr>
          <td><strong>${escapeHtml(s.name)}</strong></td>
          <td>${escapeHtml(s.deliveries)}</td>
          <td>${formatCurrency(s.value)}</td>
        </tr>
      `
    )
    .join("");
}

$("periodForm").addEventListener("submit", (e) => {
  e.preventDefault();
  loadReport();
});

document.querySelectorAll("[data-preset]").forEach((button) => {
  button.addEventListener("click", () => {
    const today = new Date();
    const start =
      button.dataset.preset === "month"
        ? new Date(today.getFullYear(), today.getMonth(), 1)
        : new Date(today.getFullYear(), 0, 1);
    $("dateFrom").value = isoDate(start);
    $("dateTo").value = isoDate(today);
    loadReport();
  });
});

$("exportMovementsButton").addEventListener("click", () => {
  const params = periodParams();
  params.set("delimiter", csvDelimiter());
  downloadFile(`/reports/movements.csv?${params}`, "stock-movements.csv");
});

if (await initProtectedPage()) {
  loadReport();
}
