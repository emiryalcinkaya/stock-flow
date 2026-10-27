import { apiFetch, readJson } from "./config.js";
import { initProtectedPage, isAdmin } from "./auth.js";
import { formatQuantity, STOCK_OUT_REASONS } from "./inventory.js";
import {
  escapeHtml,
  formatCurrency,
  formatDate,
  getErrorMessage,
  refreshIcons,
  renderEmptyRow,
  setButtonLoading,
  showToast,
  statusBadge
} from "./ui.js";

const salesHistoryTable = document.getElementById("salesHistoryTable");
const saleDetailPanel = document.getElementById("saleDetailPanel");
const salesFilterForm = document.getElementById("salesFilterForm");
const dateFromInput = document.getElementById("dateFrom");
const dateToInput = document.getElementById("dateTo");
const reasonFilter = document.getElementById("reasonFilter");

let currentUser = null;
let selectedSaleId = null;

const reasonLabel = (reason) => STOCK_OUT_REASONS[reason] || reason;

reasonFilter.innerHTML = [
  `<option value="">All reasons</option>`,
  ...Object.entries(STOCK_OUT_REASONS).map(
    ([value, label]) => `<option value="${value}">${escapeHtml(label)}</option>`
  )
].join("");

function buildSalesQuery() {
  const params = new URLSearchParams();
  if (dateFromInput.value) params.set("date_from", dateFromInput.value);
  if (dateToInput.value) params.set("date_to", dateToInput.value);
  if (reasonFilter.value) params.set("reason", reasonFilter.value);
  const query = params.toString();
  return query ? `?${query}` : "";
}

async function loadSalesHistory() {
  try {
    const response = await apiFetch(`/sales/${buildSalesQuery()}`);
    const sales = await readJson(response);

    if (!response.ok) {
      showToast(getErrorMessage(sales, "Failed to load history"), "error");
      return;
    }

    if (!sales.length) {
      renderEmptyRow(salesHistoryTable, 6, "Nothing found.");
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
              <span>View</span>
            </button>
          </td>
        </tr>
      `
      )
      .join("");

    refreshIcons();
  } catch (error) {
    console.error(error);
    showToast("Request failed", "error");
  }
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
        <div>
          <div class="metric-note">Created At</div>
          <div>${escapeHtml(formatDate(sale.created_at))}</div>
        </div>
        <div>
          <div class="metric-note">Warehouse</div>
          <div>${escapeHtml(sale.warehouse_name || "-")}</div>
        </div>
        <div>
          <div class="metric-note">User</div>
          <div>${escapeHtml(sale.cashier_name || "-")}</div>
        </div>
        <div>
          <div class="metric-note">Status</div>
          <div>${statusBadge(sale.status)}</div>
        </div>
        ${
          sale.cancelled_at
            ? `<div>
                <div class="metric-note">Cancelled At</div>
                <div>${escapeHtml(formatDate(sale.cancelled_at))}</div>
              </div>`
            : ""
        }
      </div>

      ${
        sale.note
          ? `<div>
              <div class="metric-note">Note</div>
              <div>${escapeHtml(sale.note)}</div>
            </div>`
          : ""
      }

      <div>
        <div class="metric-note">Total Value</div>
        <div class="sale-detail-total">${formatCurrency(sale.total_price)}</div>
      </div>

      <div>
        <div class="metric-note sale-detail-items-label">Items</div>
        <div class="table-wrap">
          <table class="table">
            <thead>
              <tr>
                <th>Product</th>
                <th>Qty</th>
                <th>Unit Price</th>
                <th>Total</th>
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
                <span>Cancel &amp; Return to Stock</span>
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
      showToast(getErrorMessage(sale, "Failed to load details"), "error");
      return;
    }

    selectedSaleId = sale.id;
    renderSaleDetail(sale);
  } catch (error) {
    console.error(error);
    showToast("Request failed", "error");
  }
}

async function cancelSale(saleId, button) {
  if (!window.confirm(`Cancel stock out #${saleId}? Its items will be returned to stock.`)) return;

  setButtonLoading(button, true, "Cancelling...");

  try {
    const response = await apiFetch(`/sales/${saleId}/cancel`, { method: "POST" });
    const sale = await readJson(response);

    if (!response.ok) {
      showToast(getErrorMessage(sale, "Failed to cancel"), "error");
      setButtonLoading(button, false);
      return;
    }

    showToast(`Stock out #${sale.id} cancelled`, "success");
    renderSaleDetail(sale);
    loadSalesHistory();
  } catch (error) {
    console.error(error);
    showToast("Request failed", "error");
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
  loadSalesHistory();
});

salesFilterForm.addEventListener("reset", () => {
  setTimeout(loadSalesHistory, 0);
});

currentUser = await initProtectedPage();

if (currentUser) {
  loadSalesHistory();
}
