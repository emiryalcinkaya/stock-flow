import { apiFetch, readJson } from "./config.js?v=6";
import { initProtectedPage, isAdmin } from "./auth.js?v=6";
import { csvDelimiter, t } from "./i18n.js?v=6";
import { formatQuantity, reasonLabel, reasonOptions } from "./inventory.js?v=6";
import {
  downloadFile,
  escapeHtml,
  formatCurrency,
  formatDate,
  getErrorMessage,
  PAGE_SIZE,
  refreshIcons,
  renderEmptyRow,
  renderPagination,
  setButtonLoading,
  showToast,
  statusBadge,
  totalCount
} from "./ui.js?v=6";

const salesHistoryTable = document.getElementById("salesHistoryTable");
const saleDetailPanel = document.getElementById("saleDetailPanel");
const salesFilterForm = document.getElementById("salesFilterForm");
const dateFromInput = document.getElementById("dateFrom");
const dateToInput = document.getElementById("dateTo");
const reasonFilter = document.getElementById("reasonFilter");

let currentUser = null;
let selectedSaleId = null;
let skip = 0;

function buildFilters() {
  const params = new URLSearchParams();
  if (dateFromInput.value) params.set("date_from", dateFromInput.value);
  if (dateToInput.value) params.set("date_to", dateToInput.value);
  if (reasonFilter.value) params.set("reason", reasonFilter.value);
  return params;
}

async function loadSalesHistory() {
  try {
    const params = buildFilters();
    params.set("skip", skip);
    params.set("limit", PAGE_SIZE);
    const response = await apiFetch(`/sales/?${params}`);
    const sales = await readJson(response);

    if (!response.ok) {
      showToast(getErrorMessage(sales, t("history.loadFailed")), "error");
      return;
    }

    renderPagination(document.getElementById("salesPager"), {
      total: totalCount(response),
      skip,
      onPage: (newSkip) => {
        skip = newSkip;
        loadSalesHistory();
      }
    });

    if (!sales.length) {
      renderEmptyRow(salesHistoryTable, 6, t("common.nothingFound"));
      return;
    }

    salesHistoryTable.innerHTML = sales
      .map(
        (sale) => `
        <tr class="${sale.id === selectedSaleId ? "row-selected" : ""}">
          <td>#${escapeHtml(sale.id)}</td>
          <td>${escapeHtml(reasonLabel(sale.reason))}</td>
          <td>${formatCurrency(sale.total_price)}</td>
          <td>${statusBadge(sale.status)}</td>
          <td>${escapeHtml(formatDate(sale.created_at))}</td>
          <td>
            <button class="btn btn-secondary icon-btn" data-action="view" data-id="${sale.id}">
              <i data-lucide="eye"></i>
              <span>${escapeHtml(t("action.view"))}</span>
            </button>
          </td>
        </tr>
      `
      )
      .join("");

    refreshIcons();
  } catch (error) {
    console.error(error);
    showToast(t("common.requestFailed"), "error");
  }
}

function detailField(labelKey, value) {
  return `
    <div>
      <div class="metric-note">${escapeHtml(t(labelKey))}</div>
      <div>${value}</div>
    </div>
  `;
}

function renderSaleDetail(sale) {
  const canCancel = isAdmin(currentUser) && sale.status === "completed";

  saleDetailPanel.innerHTML = `
    <div class="sale-detail">
      <div>
        <div class="metric-note">${escapeHtml(reasonLabel(sale.reason))}</div>
        <div class="stat-value sale-detail-id">#${escapeHtml(sale.id)}</div>
      </div>

      <div class="sale-detail-meta">
        ${detailField("col.date", escapeHtml(formatDate(sale.created_at)))}
        ${detailField("col.warehouse", escapeHtml(sale.warehouse_name || "-"))}
        ${detailField("col.user", escapeHtml(sale.cashier_name || "-"))}
        ${detailField("col.status", statusBadge(sale.status))}
        ${sale.cancelled_at ? detailField("history.cancelledAt", escapeHtml(formatDate(sale.cancelled_at))) : ""}
      </div>

      ${sale.note ? detailField("field.note", escapeHtml(sale.note)) : ""}

      <div>
        <div class="metric-note">${escapeHtml(t("stockOut.totalValue"))}</div>
        <div class="sale-detail-total">${formatCurrency(sale.total_price)}</div>
      </div>

      <div>
        <div class="metric-note sale-detail-items-label">${escapeHtml(t("stockOut.items"))}</div>
        <div class="table-wrap">
          <table class="table">
            <thead>
              <tr>
                <th>${escapeHtml(t("col.product"))}</th>
                <th>${escapeHtml(t("col.quantity"))}</th>
                <th>${escapeHtml(t("col.unitPrice"))}</th>
                <th>${escapeHtml(t("col.total"))}</th>
              </tr>
            </thead>
            <tbody>
              ${sale.items
                .map(
                  (item) => `
                  <tr>
                    <td>${escapeHtml(item.product_name)}</td>
                    <td>${escapeHtml(formatQuantity(item.quantity, item.unit))}</td>
                    <td>${formatCurrency(item.unit_price)}</td>
                    <td>${formatCurrency(item.total_price)}</td>
                  </tr>
                `
                )
                .join("")}
            </tbody>
          </table>
        </div>
      </div>

      ${
        canCancel
          ? `<div>
              <button class="btn btn-danger icon-btn" data-action="cancel" data-id="${sale.id}">
                <i data-lucide="undo-2"></i>
                <span>${escapeHtml(t("history.cancelButton"))}</span>
              </button>
            </div>`
          : ""
      }
    </div>
  `;

  refreshIcons();
}

async function viewSaleDetail(saleId) {
  try {
    const response = await apiFetch(`/sales/${saleId}`);
    const sale = await readJson(response);

    if (!response.ok) {
      showToast(getErrorMessage(sale, t("history.loadFailed")), "error");
      return;
    }

    selectedSaleId = sale.id;
    renderSaleDetail(sale);
  } catch (error) {
    console.error(error);
    showToast(t("common.requestFailed"), "error");
  }
}

async function cancelSale(saleId, button) {
  if (!window.confirm(t("history.cancelConfirm", { id: saleId }))) return;

  setButtonLoading(button, true, t("common.saving"));

  try {
    const response = await apiFetch(`/sales/${saleId}/cancel`, { method: "POST" });
    const sale = await readJson(response);

    if (!response.ok) {
      showToast(getErrorMessage(sale, t("history.cancelFailed")), "error");
      setButtonLoading(button, false);
      return;
    }

    showToast(t("history.cancelled", { id: sale.id }), "success");
    renderSaleDetail(sale);
    loadSalesHistory();
  } catch (error) {
    console.error(error);
    showToast(t("common.requestFailed"), "error");
    setButtonLoading(button, false);
  }
}

document.addEventListener("click", (e) => {
  const button = e.target.closest("[data-action]");
  if (!button) return;

  const saleId = Number(button.dataset.id);
  if (button.dataset.action === "view") viewSaleDetail(saleId);
  if (button.dataset.action === "cancel") cancelSale(saleId, button);
});

salesFilterForm.addEventListener("submit", (e) => {
  e.preventDefault();
  skip = 0;
  loadSalesHistory();
});

salesFilterForm.addEventListener("reset", () => {
  skip = 0;
  setTimeout(loadSalesHistory, 0);
});

document.getElementById("exportButton").addEventListener("click", () => {
  const params = buildFilters();
  params.delete("reason");
  params.set("delimiter", csvDelimiter());
  downloadFile(`/reports/stock-outs.csv?${params}`, "stock-outs.csv");
});

currentUser = await initProtectedPage();

if (currentUser) {
  reasonFilter.innerHTML = reasonOptions("", { includeAll: true });
  loadSalesHistory();
}
