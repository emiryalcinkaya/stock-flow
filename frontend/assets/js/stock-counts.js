import { apiFetch, readJson } from "./config.js?v=7";
import { initProtectedPage, isAdmin } from "./auth.js?v=8";
import { t } from "./i18n.js?v=7";
import {
  categoryOptions,
  formatQuantity,
  loadCategories,
  loadUnits,
  loadWarehouses,
  optionalNumber,
  quantityStep,
  warehouseOptions
} from "./inventory.js?v=7";
import {
  escapeHtml,
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
} from "./ui.js?v=7";

const $ = (id) => document.getElementById(id);

let currentUser = null;
let units = [];
let warehouses = [];
let skip = 0;
let currentCount = null;
// Unsaved inputs, product id -> value typed by the user ("" = cleared).
let edits = new Map();

// ----- List -----

async function loadCounts() {
  const response = await apiFetch(`/stock-counts?skip=${skip}&limit=${PAGE_SIZE}`);
  const counts = await readJson(response);
  if (!response.ok) {
    showToast(getErrorMessage(counts, t("count.loadFailed")), "error");
    return;
  }

  renderPagination($("countsPager"), {
    total: totalCount(response),
    skip,
    onPage: (newSkip) => {
      skip = newSkip;
      loadCounts();
    }
  });

  if (!counts.length) {
    renderEmptyRow($("countsTable"), 8, t("count.empty"));
    return;
  }

  $("countsTable").innerHTML = counts
    .map(
      (count) => `
        <tr class="${count.id === currentCount?.id ? "row-selected" : ""}">
          <td>#${escapeHtml(count.id)}</td>
          <td>${escapeHtml(count.warehouse_name)}</td>
          <td>${escapeHtml(count.category_name || t("count.allProducts"))}</td>
          <td>${statusBadge(count.status)}</td>
          <td>${escapeHtml(t("count.progressValue", { counted: count.counted_count, total: count.line_count }))}</td>
          <td>${escapeHtml(count.created_by_name || "-")}</td>
          <td>${escapeHtml(formatDate(count.created_at))}</td>
          <td>
            <button class="btn btn-secondary icon-btn" data-open-count="${count.id}">
              <i data-lucide="${count.status === "open" ? "clipboard-pen" : "eye"}"></i>
              <span>${escapeHtml(t(count.status === "open" ? "count.continue" : "action.view"))}</span>
            </button>
          </td>
        </tr>
      `
    )
    .join("");
  refreshIcons();
}

// ----- Detail -----

function lineValue(line) {
  if (edits.has(line.product_id)) return edits.get(line.product_id);
  return line.counted_quantity ?? "";
}

function differenceFor(line) {
  if (line.difference !== null) return line.difference; // final, stored on completion
  const value = lineValue(line);
  return value === "" ? null : Math.round((Number(value) - line.expected_quantity) * 1000) / 1000;
}

function differenceCell(line) {
  const diff = differenceFor(line);
  if (diff === null) return `<span class="metric-note">-</span>`;
  const cls = diff < 0 ? "stock-low" : diff > 0 ? "stock-good" : "";
  return `<span class="${cls}">${diff > 0 ? "+" : ""}${escapeHtml(formatQuantity(diff, line.unit))}</span>`;
}

function visibleLines() {
  const search = $("lineSearch").value.trim().toLowerCase();
  return currentCount.lines.filter((line) => {
    if (search && !`${line.product_name} ${line.product_barcode}`.toLowerCase().includes(search)) return false;
    if ($("onlyUncounted").checked && lineValue(line) !== "") return false;
    if ($("onlyDifferences").checked) {
      const diff = differenceFor(line);
      if (diff === null || diff === 0) return false;
    }
    return true;
  });
}

function renderLines() {
  const editable = currentCount.status === "open";
  const lines = visibleLines();

  if (!lines.length) {
    renderEmptyRow($("countLines"), 5, t("common.nothingFound"));
  } else {
    $("countLines").innerHTML = lines
      .map(
        (line) => `
          <tr>
            <td><strong>${escapeHtml(line.product_name)}</strong></td>
            <td>${escapeHtml(line.product_barcode)}</td>
            <td>${escapeHtml(formatQuantity(line.expected_quantity, line.unit))}</td>
            <td>${
              editable
                ? `<input class="input count-input" type="number" min="0" step="${quantityStep(units, line.unit)}"
                     data-product-id="${line.product_id}" value="${escapeHtml(lineValue(line))}"
                     aria-label="${escapeHtml(t("count.counted"))}: ${escapeHtml(line.product_name)}" />`
                : escapeHtml(line.counted_quantity === null ? "-" : formatQuantity(line.counted_quantity, line.unit))
            }</td>
            <td data-diff-for="${line.product_id}">${differenceCell(line)}</td>
          </tr>
        `
      )
      .join("");
  }

  const counted = currentCount.lines.filter((line) => lineValue(line) !== "").length;
  $("countProgress").textContent = t("count.progressValue", { counted, total: currentCount.lines.length });
}

function renderDetail() {
  const count = currentCount;
  const editable = count.status === "open";

  $("countDetail").hidden = false;
  $("countTitle").innerHTML = `${escapeHtml(t("count.titleWithId", { id: count.id }))} ${statusBadge(count.status)}`;
  $("countMeta").textContent = [
    count.warehouse_name,
    count.category_name || t("count.allProducts"),
    formatDate(count.created_at),
    count.note
  ]
    .filter(Boolean)
    .join(" · ");

  $("saveCountButton").hidden = !editable;
  $("completeCountButton").hidden = !editable || !isAdmin(currentUser);
  $("cancelCountButton").hidden = !editable || !isAdmin(currentUser);

  renderLines();
}

async function openCount(countId, { scroll = true } = {}) {
  const response = await apiFetch(`/stock-counts/${countId}`);
  const count = await readJson(response);
  if (!response.ok) {
    showToast(getErrorMessage(count, t("count.loadFailed")), "error");
    return;
  }

  currentCount = count;
  edits = new Map();
  renderDetail();
  loadCounts();
  if (scroll) $("countDetail").scrollIntoView({ behavior: "smooth", block: "start" });
}

async function saveEdits({ quiet = false } = {}) {
  if (!edits.size) return true;

  const lines = [...edits].map(([productId, value]) => ({
    product_id: productId,
    counted_quantity: optionalNumber(value)
  }));
  const response = await apiFetch(`/stock-counts/${currentCount.id}`, {
    method: "PATCH",
    body: JSON.stringify({ lines })
  });
  const data = await readJson(response);
  if (!response.ok) {
    showToast(getErrorMessage(data, t("count.saveFailed")), "error");
    return false;
  }

  currentCount = data;
  edits = new Map();
  renderDetail();
  if (!quiet) showToast(t("count.saved"), "success");
  return true;
}

// ----- Events -----

$("countLines").addEventListener("input", (e) => {
  const input = e.target.closest("[data-product-id]");
  if (!input) return;

  const productId = Number(input.dataset.productId);
  edits.set(productId, input.value);
  const line = currentCount.lines.find((l) => l.product_id === productId);
  document.querySelector(`[data-diff-for="${productId}"]`).innerHTML = differenceCell(line);
  const counted = currentCount.lines.filter((l) => lineValue(l) !== "").length;
  $("countProgress").textContent = t("count.progressValue", { counted, total: currentCount.lines.length });
});

// Enter moves to the next product, handy with a barcode scanner or numpad.
$("countLines").addEventListener("keydown", (e) => {
  if (e.key !== "Enter" || !e.target.matches(".count-input")) return;
  e.preventDefault();
  const inputs = [...document.querySelectorAll(".count-input")];
  inputs[inputs.indexOf(e.target) + 1]?.focus();
});

["lineSearch", "onlyUncounted", "onlyDifferences"].forEach((id) => {
  $(id).addEventListener(id === "lineSearch" ? "input" : "change", () => currentCount && renderLines());
});

$("saveCountButton").addEventListener("click", async (e) => {
  const button = e.currentTarget;
  setButtonLoading(button, true, t("common.saving"));
  await saveEdits();
  setButtonLoading(button, false);
});

$("completeCountButton").addEventListener("click", async (e) => {
  const button = e.currentTarget;
  if (!window.confirm(t("count.completeConfirm"))) return;

  setButtonLoading(button, true, t("common.saving"));
  try {
    if (!(await saveEdits({ quiet: true }))) return;

    const response = await apiFetch(`/stock-counts/${currentCount.id}/complete`, { method: "POST" });
    const data = await readJson(response);
    if (!response.ok) {
      showToast(getErrorMessage(data, t("count.completeFailed")), "error");
      return;
    }

    currentCount = data;
    const changed = data.lines.filter((line) => line.difference !== null && line.difference !== 0).length;
    showToast(t("count.completed", { count: changed }), "success");
    renderDetail();
    loadCounts();
  } finally {
    setButtonLoading(button, false);
  }
});

$("cancelCountButton").addEventListener("click", async () => {
  if (!window.confirm(t("count.cancelConfirm"))) return;

  const response = await apiFetch(`/stock-counts/${currentCount.id}/cancel`, { method: "POST" });
  const data = await readJson(response);
  if (!response.ok) {
    showToast(getErrorMessage(data, t("count.cancelFailed")), "error");
    return;
  }
  currentCount = data;
  edits = new Map();
  showToast(t("count.cancelled"), "success");
  renderDetail();
  loadCounts();
});

$("countsTable").addEventListener("click", async (e) => {
  const button = e.target.closest("[data-open-count]");
  if (!button) return;
  if (edits.size && !window.confirm(t("count.unsavedConfirm"))) return;
  openCount(Number(button.dataset.openCount));
});

$("newCountForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const button = $("startCountButton");
  setButtonLoading(button, true, t("common.saving"));

  try {
    const payload = {
      category_id: optionalNumber($("countCategory").value),
      note: $("countNote").value
    };
    if (warehouses.length > 1) payload.warehouse_id = Number($("countWarehouse").value);

    const response = await apiFetch("/stock-counts", { method: "POST", body: JSON.stringify(payload) });
    const data = await readJson(response);
    if (!response.ok) {
      showToast(getErrorMessage(data, t("count.startFailed")), "error");
      return;
    }

    showToast(t("count.started"), "success");
    $("newCountForm").reset();
    currentCount = data;
    edits = new Map();
    renderDetail();
    loadCounts();
    $("countDetail").scrollIntoView({ behavior: "smooth", block: "start" });
  } finally {
    setButtonLoading(button, false);
  }
});

window.addEventListener("beforeunload", (e) => {
  if (edits.size) e.preventDefault();
});

currentUser = await initProtectedPage();

if (currentUser) {
  try {
    let categories;
    [units, warehouses, categories] = await Promise.all([loadUnits(), loadWarehouses(), loadCategories()]);
    $("countWarehouse").innerHTML = warehouseOptions(warehouses);
    $("countCategory").innerHTML = categoryOptions(categories, null, t("count.allProducts"));
    document.querySelectorAll("[data-multi-warehouse]").forEach((el) => {
      el.hidden = warehouses.length < 2;
    });
  } catch (error) {
    console.error(error);
    showToast(t("products.lookupsFailed"), "error");
  }

  await loadCounts();

  // Jump straight into an open count, since that's what people come back for.
  const response = await apiFetch("/stock-counts?status=open&limit=1");
  const open = response.ok ? await readJson(response) : [];
  if (open.length) openCount(open[0].id, { scroll: false });
}
