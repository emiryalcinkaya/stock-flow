import { apiFetch, readJson } from "./config.js?v=7";
import { initProtectedPage, isAdmin } from "./auth.js?v=8";
import { csvDelimiter, t } from "./i18n.js?v=7";
import {
  categoryOptions,
  formatQuantity,
  loadCategories,
  loadSuppliers,
  loadUnits,
  loadWarehouses,
  movementLabel,
  optionalNumber,
  quantityStep,
  supplierOptions,
  unitOptions,
  warehouseOptions
} from "./inventory.js?v=7";
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
  totalCount
} from "./ui.js?v=7";

const $ = (id) => document.getElementById(id);

const productsTable = $("productsTable");
const archivedProductsTable = $("archivedProductsTable");
const productForm = $("productForm");
const addProductButton = $("addProductButton");
const productSearch = $("productSearch");
const categoryFilter = $("categoryFilter");
const lowStockFilter = $("lowStockFilter");
const sortSelect = $("sortSelect");

const formCategory = $("category");
const formUnit = $("unit");
const formWarehouse = $("warehouse");
const formStock = $("stock_quantity");
const formMinStock = $("min_stock");

const stockModalOverlay = $("stockModalOverlay");
const stockModalQuantity = $("stockModalQuantity");
const stockModalWarehouse = $("stockModalWarehouse");
const stockModalSupplier = $("stockModalSupplier");
const stockModalUnitCost = $("stockModalUnitCost");
const stockModalDocument = $("stockModalDocument");
const stockModalNote = $("stockModalNote");
const confirmStockModalBtn = $("confirmStockModalBtn");

const transferModalOverlay = $("transferModalOverlay");
const transferFrom = $("transferFrom");
const transferTo = $("transferTo");
const transferQuantity = $("transferQuantity");
const transferNote = $("transferNote");
const confirmTransferBtn = $("confirmTransferBtn");

const historyModalOverlay = $("historyModalOverlay");
const historyTable = $("historyTable");

const editModalOverlay = $("editModalOverlay");
const deleteModalOverlay = $("deleteModalOverlay");
const importModalOverlay = $("importModalOverlay");
const importFile = $("importFile");
const importResult = $("importResult");
const confirmImportBtn = $("confirmImportBtn");

let currentUser = null;
let products = [];
let units = [];
let categories = [];
let warehouses = [];
let suppliers = [];
let productsSkip = 0;
let archivedSkip = 0;
let currentStockProduct = null;
let currentStockAction = null;
let currentTransferProduct = null;
let currentEditProductId = null;
let currentDeleteProductId = null;
let importCsvText = null;

const hasManyWarehouses = () => warehouses.length > 1;

// Dashboard links here with ?low_stock=1
if (new URLSearchParams(window.location.search).has("low_stock")) {
  lowStockFilter.checked = true;
}

function findProduct(id) {
  return products.find((product) => product.id === id);
}

// ----- Lookups -----

async function loadLookups() {
  [units, categories, warehouses, suppliers] = await Promise.all([
    loadUnits(),
    loadCategories(),
    loadWarehouses(),
    loadSuppliers()
  ]);

  formUnit.innerHTML = unitOptions(units);
  $("editUnit").innerHTML = unitOptions(units);
  formCategory.innerHTML = categoryOptions(categories);
  categoryFilter.innerHTML = categoryOptions(categories, null, t("common.allCategories"));
  formWarehouse.innerHTML = warehouseOptions(warehouses);

  document.querySelectorAll("[data-multi-warehouse]").forEach((element) => {
    element.hidden = !hasManyWarehouses();
  });

  syncFormSteps();
}

function syncFormSteps() {
  const step = quantityStep(units, formUnit.value);
  formStock.step = step;
  formMinStock.step = step;
}

formUnit.addEventListener("change", syncFormSteps);
$("editUnit").addEventListener("change", () => {
  $("editMinStock").step = quantityStep(units, $("editUnit").value);
});

// ----- Product list -----

function buildProductQuery() {
  const params = new URLSearchParams({ skip: productsSkip, limit: PAGE_SIZE });
  const search = productSearch.value.trim();
  if (search) params.set("search", search);
  if (categoryFilter.value) params.set("category_id", categoryFilter.value);
  if (lowStockFilter.checked) params.set("low_stock", "true");
  if (sortSelect.value !== "id") params.set("sort", sortSelect.value);
  return `?${params}`;
}

async function loadProducts() {
  try {
    const response = await apiFetch(`/products/${buildProductQuery()}`);
    const data = await readJson(response);

    if (!response.ok) {
      showToast(getErrorMessage(data, t("products.loadFailed")), "error");
      return;
    }

    products = data;
    renderProducts();
    renderPagination($("productsPager"), {
      total: totalCount(response),
      skip: productsSkip,
      onPage: (skip) => {
        productsSkip = skip;
        loadProducts();
      }
    });
  } catch (error) {
    console.error(error);
    showToast(t("common.requestFailed"), "error");
  }
}

// Filters change the result set, so go back to the first page.
function reloadFromFirstPage() {
  productsSkip = 0;
  loadProducts();
}

function renderProducts() {
  if (!products.length) {
    renderEmptyRow(productsTable, 7, t("products.empty"));
    return;
  }

  productsTable.innerHTML = products
    .map(
      (product) => `
        <tr>
          <td>${escapeHtml(product.id)}</td>
          <td><strong>${escapeHtml(product.name)}</strong></td>
          <td>${escapeHtml(product.category_name || "-")}</td>
          <td>${escapeHtml(product.barcode)}</td>
          <td>${product.price === null ? "-" : formatCurrency(product.price)}</td>
          <td class="${product.is_low_stock ? "stock-low" : "stock-good"}" title="${
            product.min_stock === null
              ? ""
              : escapeHtml(t("products.minimumTitle", { quantity: formatQuantity(product.min_stock, product.unit) }))
          }">
            ${escapeHtml(formatQuantity(product.stock_quantity, product.unit))}
          </td>
          <td>${renderProductActions(product.id)}</td>
        </tr>
      `
    )
    .join("");

  refreshIcons();
}

function actionButton(action, id, icon, labelKey, danger = false) {
  return `
    <button class="btn ${danger ? "btn-danger" : "btn-secondary"} icon-btn" data-action="${action}" data-id="${id}">
      <i data-lucide="${icon}"></i>
      <span>${escapeHtml(t(labelKey))}</span>
    </button>
  `;
}

function renderProductActions(productId) {
  const history = actionButton("history", productId, "history", "action.history");
  if (!isAdmin(currentUser)) {
    return `<div class="row-actions">${history}</div>`;
  }

  return `
    <div class="row-actions">
      ${actionButton("edit", productId, "square-pen", "action.edit")}
      ${actionButton("increase", productId, "package-plus", "action.stockIn")}
      ${actionButton("decrease", productId, "package-minus", "action.stockOut")}
      ${hasManyWarehouses() ? actionButton("transfer", productId, "arrow-left-right", "action.transfer") : ""}
      ${history}
      ${actionButton("archive", productId, "archive", "action.archive", true)}
    </div>
  `;
}

async function loadArchivedProducts() {
  try {
    const response = await apiFetch(`/products/?status=archived&skip=${archivedSkip}&limit=${PAGE_SIZE}`);
    const archived = await readJson(response);

    if (!response.ok) {
      showToast(getErrorMessage(archived, t("products.loadFailed")), "error");
      return;
    }

    renderPagination($("archivedPager"), {
      total: totalCount(response),
      skip: archivedSkip,
      onPage: (skip) => {
        archivedSkip = skip;
        loadArchivedProducts();
      }
    });

    if (!archived.length) {
      renderEmptyRow(archivedProductsTable, 4, t("products.noArchived"));
      return;
    }

    archivedProductsTable.innerHTML = archived
      .map(
        (product) => `
          <tr>
            <td>${escapeHtml(product.id)}</td>
            <td><strong>${escapeHtml(product.name)}</strong></td>
            <td>${escapeHtml(product.barcode)}</td>
            <td>${actionButton("restore", product.id, "archive-restore", "action.restore")}</td>
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

function reloadAll() {
  loadProducts();
  if (isAdmin(currentUser)) loadArchivedProducts();
}

async function submitJson(endpoint, method, body, fallbackError) {
  const response = await apiFetch(endpoint, {
    method,
    body: body === undefined ? undefined : JSON.stringify(body)
  });
  const data = await readJson(response);

  if (!response.ok) {
    showToast(getErrorMessage(data, fallbackError), "error");
    return null;
  }
  return data;
}

async function fetchStockLevels(productId) {
  const response = await apiFetch(`/products/${productId}/stock-levels`);
  return response.ok ? readJson(response) : [];
}

function renderLevels(container, levels, unit) {
  if (!hasManyWarehouses()) {
    container.innerHTML = "";
    return;
  }

  container.innerHTML = levels.length
    ? levels
        .map(
          (level) => `
            <div class="stock-pill">
              ${escapeHtml(level.warehouse_name)}: ${escapeHtml(formatQuantity(level.quantity, unit))}
            </div>
          `
        )
        .join("")
    : `<div class="metric-note">${escapeHtml(t("transfer.noStock"))}</div>`;
}

// ----- Add product -----

productForm.addEventListener("submit", async (e) => {
  e.preventDefault();

  const payload = {
    name: $("name").value.trim(),
    barcode: $("barcode").value.trim(),
    category_id: optionalNumber(formCategory.value),
    unit: formUnit.value,
    stock_quantity: Number(formStock.value || 0),
    min_stock: optionalNumber(formMinStock.value),
    price: optionalNumber($("price").value),
    cost_price: optionalNumber($("cost_price").value)
  };
  if (hasManyWarehouses()) payload.warehouse_id = Number(formWarehouse.value);

  setButtonLoading(addProductButton, true, t("common.saving"));

  try {
    const created = await submitJson("/products/", "POST", payload, t("products.addFailed"));
    if (!created) return;

    showToast(t("products.added"), "success");
    productForm.reset();
    formUnit.value = "pcs";
    syncFormSteps();
    loadProducts();
  } catch (error) {
    console.error(error);
    showToast(t("common.requestFailed"), "error");
  } finally {
    setButtonLoading(addProductButton, false);
  }
});

let searchTimer = null;
productSearch.addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(reloadFromFirstPage, 250);
});
categoryFilter.addEventListener("change", reloadFromFirstPage);
lowStockFilter.addEventListener("change", reloadFromFirstPage);
sortSelect.addEventListener("change", reloadFromFirstPage);

// ----- Modals -----

function openModal(overlay) {
  overlay.classList.add("show");
  const firstInput = overlay.querySelector("input:not([type=file])");
  if (firstInput) firstInput.focus();
}

function closeModal(overlay) {
  overlay.classList.remove("show");
}

function openStockModal(productId, action) {
  const product = findProduct(productId);
  if (!product) return;

  currentStockProduct = product;
  currentStockAction = action;
  const stockIn = action === "increase";

  stockModalQuantity.value = "";
  stockModalQuantity.step = quantityStep(units, product.unit);
  stockModalNote.value = "";
  stockModalUnitCost.value = product.cost_price ?? "";
  stockModalDocument.value = "";
  stockModalWarehouse.innerHTML = warehouseOptions(warehouses);
  stockModalSupplier.innerHTML = supplierOptions(suppliers);
  stockModalOverlay.querySelectorAll("[data-stock-in-only]").forEach((field) => {
    field.hidden = !stockIn;
  });

  $("stockModalTitle").textContent = t(stockIn ? "action.stockIn" : "action.stockOut");
  $("stockModalSubtitle").textContent = t("stock.current", {
    product: product.name,
    quantity: formatQuantity(product.stock_quantity, product.unit)
  });
  openModal(stockModalOverlay);
}

async function openTransferModal(productId) {
  const product = findProduct(productId);
  if (!product) return;

  currentTransferProduct = product;
  $("transferModalSubtitle").textContent = product.name;
  transferQuantity.value = "";
  transferQuantity.step = quantityStep(units, product.unit);
  transferNote.value = "";

  const levels = await fetchStockLevels(productId);
  const withStock = levels.find((level) => level.quantity > 0);
  transferFrom.innerHTML = warehouseOptions(warehouses, withStock?.warehouse_id);
  transferTo.innerHTML = warehouseOptions(
    warehouses,
    warehouses.find((w) => w.id !== Number(transferFrom.value))?.id
  );
  renderLevels($("transferLevels"), levels, product.unit);
  openModal(transferModalOverlay);
}

function movementDetails(movement) {
  const parts = [];
  if (movement.supplier_name) parts.push(movement.supplier_name);
  if (movement.document_no) parts.push(`#${movement.document_no}`);
  if (movement.unit_cost !== null) parts.push(t("history.unitCost", { cost: formatCurrency(movement.unit_cost) }));
  if (movement.note) parts.push(movement.note);
  return parts.join(" · ");
}

async function openHistoryModal(productId) {
  const product = findProduct(productId);
  if (!product) return;

  $("historyModalSubtitle").textContent = t("history.subtitle", {
    product: product.name,
    quantity: formatQuantity(product.stock_quantity, product.unit)
  });
  renderEmptyRow(historyTable, 7, t("common.loading"));
  $("historyLevels").innerHTML = "";
  openModal(historyModalOverlay);

  try {
    const [levels, response] = await Promise.all([
      fetchStockLevels(productId),
      apiFetch(`/products/${productId}/movements`)
    ]);
    const movements = await readJson(response);

    if (!response.ok) {
      renderEmptyRow(historyTable, 7, getErrorMessage(movements, t("history.loadFailed")));
      return;
    }

    renderLevels($("historyLevels"), levels, product.unit);

    if (!movements.length) {
      renderEmptyRow(historyTable, 7, t("history.empty"));
      return;
    }

    historyTable.innerHTML = movements
      .map(
        (movement) => `
          <tr>
            <td>${escapeHtml(formatDate(movement.created_at))}</td>
            <td>${escapeHtml(movementLabel(movement.reason))}</td>
            <td>${escapeHtml(movement.warehouse_name || "-")}</td>
            <td class="${movement.change < 0 ? "stock-low" : "stock-good"}">
              ${movement.change > 0 ? "+" : ""}${escapeHtml(formatQuantity(movement.change, product.unit))}
            </td>
            <td>${escapeHtml(formatQuantity(movement.quantity_after, product.unit))}</td>
            <td>${escapeHtml(movement.username || "-")}</td>
            <td>${escapeHtml(movementDetails(movement))}</td>
          </tr>
        `
      )
      .join("");
  } catch (error) {
    console.error(error);
    renderEmptyRow(historyTable, 7, t("common.requestFailed"));
  }
}

function openEditModal(productId) {
  const product = findProduct(productId);
  if (!product) return;

  currentEditProductId = productId;
  $("editName").value = product.name;
  $("editBarcode").value = product.barcode;
  $("editCategory").innerHTML = categoryOptions(categories, product.category_id);
  $("editUnit").innerHTML = unitOptions(units, product.unit);
  $("editMinStock").value = product.min_stock ?? "";
  $("editMinStock").step = quantityStep(units, product.unit);
  $("editPrice").value = product.price ?? "";
  $("editCostPrice").value = product.cost_price ?? "";
  openModal(editModalOverlay);
}

function openDeleteModal(productId) {
  const product = findProduct(productId);
  if (!product) return;

  currentDeleteProductId = productId;
  $("deleteModalText").textContent = t("archive.question", { product: product.name });
  openModal(deleteModalOverlay);
}

async function restoreProduct(productId) {
  try {
    const restored = await submitJson(`/products/${productId}/restore`, "POST", undefined, t("products.restoreFailed"));
    if (!restored) return;

    showToast(t("products.restored"), "success");
    reloadAll();
  } catch (error) {
    console.error(error);
    showToast(t("common.requestFailed"), "error");
  }
}

const rowActions = {
  edit: openEditModal,
  increase: (id) => openStockModal(id, "increase"),
  decrease: (id) => openStockModal(id, "decrease"),
  transfer: openTransferModal,
  history: openHistoryModal,
  archive: openDeleteModal,
  restore: restoreProduct
};

document.addEventListener("click", (e) => {
  const button = e.target.closest("[data-action]");
  if (!button) return;

  const handler = rowActions[button.dataset.action];
  if (handler) handler(Number(button.dataset.id));
});

confirmStockModalBtn.addEventListener("click", async () => {
  const quantity = Number(stockModalQuantity.value);

  if (!quantity || quantity <= 0) {
    showToast(t("common.invalidQuantity"), "error");
    return;
  }

  const payload = { quantity, note: stockModalNote.value };
  if (hasManyWarehouses()) payload.warehouse_id = Number(stockModalWarehouse.value);
  if (currentStockAction === "increase") {
    payload.supplier_id = optionalNumber(stockModalSupplier.value);
    payload.unit_cost = optionalNumber(stockModalUnitCost.value);
    payload.document_no = stockModalDocument.value;
  }

  setButtonLoading(confirmStockModalBtn, true, t("common.saving"));

  try {
    const updated = await submitJson(
      `/products/${currentStockProduct.id}/${currentStockAction}-stock`,
      "POST",
      payload,
      t("stock.updateFailed")
    );
    if (!updated) return;

    showToast(t("stock.updated"), "success");
    closeModal(stockModalOverlay);
    loadProducts();
  } catch (error) {
    console.error(error);
    showToast(t("common.requestFailed"), "error");
  } finally {
    setButtonLoading(confirmStockModalBtn, false);
  }
});

confirmTransferBtn.addEventListener("click", async () => {
  const quantity = Number(transferQuantity.value);

  if (!quantity || quantity <= 0) {
    showToast(t("common.invalidQuantity"), "error");
    return;
  }

  setButtonLoading(confirmTransferBtn, true, t("common.saving"));

  try {
    const updated = await submitJson(
      `/products/${currentTransferProduct.id}/transfer`,
      "POST",
      {
        from_warehouse_id: Number(transferFrom.value),
        to_warehouse_id: Number(transferTo.value),
        quantity,
        note: transferNote.value
      },
      t("transfer.failed")
    );
    if (!updated) return;

    showToast(t("transfer.done"), "success");
    closeModal(transferModalOverlay);
    loadProducts();
  } catch (error) {
    console.error(error);
    showToast(t("common.requestFailed"), "error");
  } finally {
    setButtonLoading(confirmTransferBtn, false);
  }
});

$("saveEditModalBtn").addEventListener("click", async (e) => {
  const button = e.currentTarget;
  const payload = {
    name: $("editName").value.trim(),
    barcode: $("editBarcode").value.trim(),
    category_id: optionalNumber($("editCategory").value),
    unit: $("editUnit").value,
    min_stock: optionalNumber($("editMinStock").value),
    price: optionalNumber($("editPrice").value),
    cost_price: optionalNumber($("editCostPrice").value)
  };

  setButtonLoading(button, true, t("common.saving"));

  try {
    const updated = await submitJson(`/products/${currentEditProductId}`, "PATCH", payload, t("edit.failed"));
    if (!updated) return;

    showToast(t("edit.saved"), "success");
    closeModal(editModalOverlay);
    loadProducts();
  } catch (error) {
    console.error(error);
    showToast(t("common.requestFailed"), "error");
  } finally {
    setButtonLoading(button, false);
  }
});

$("confirmDeleteModalBtn").addEventListener("click", async (e) => {
  const button = e.currentTarget;
  setButtonLoading(button, true, t("common.saving"));

  try {
    const result = await submitJson(`/products/${currentDeleteProductId}`, "DELETE", undefined, t("archive.failed"));
    if (!result) return;

    showToast(t("archive.done"), "success");
    closeModal(deleteModalOverlay);
    reloadAll();
  } catch (error) {
    console.error(error);
    showToast(t("common.requestFailed"), "error");
  } finally {
    setButtonLoading(button, false);
  }
});

// ----- CSV export / import -----

$("exportButton").addEventListener("click", () => {
  downloadFile(`/products/export.csv?delimiter=${csvDelimiter()}`, "products.csv");
});

$("importTemplateButton").addEventListener("click", () => {
  downloadFile(`/products/export.csv?delimiter=${csvDelimiter()}`, "products-template.csv");
});

$("importButton").addEventListener("click", () => {
  importCsvText = null;
  importFile.value = "";
  $("importFileName").textContent = "";
  importResult.innerHTML = "";
  confirmImportBtn.disabled = true;
  openModal(importModalOverlay);
});

function renderImportResult(result) {
  const list = (items, cls) =>
    items.length
      ? `<ul class="import-list ${cls}">${items
          .slice(0, 50)
          .map((item) => `<li>${escapeHtml(t("import.row", { row: item.row }))}: ${escapeHtml(item.message)}</li>`)
          .join("")}</ul>`
      : "";

  const summary = t(result.saved ? "import.savedSummary" : "import.previewSummary", {
    created: result.created,
    updated: result.updated,
    categories: result.categories_created
  });

  importResult.innerHTML = `
    <div class="import-summary ${result.errors.length ? "has-errors" : ""}">${escapeHtml(summary)}</div>
    ${result.errors.length ? `<div class="metric-note">${escapeHtml(t("import.fixErrors"))}</div>` : ""}
    ${list(result.errors, "is-error")}
    ${list(result.warnings, "is-warning")}
  `;
}

async function runImport(dryRun) {
  const response = await apiFetch("/products/import", {
    method: "POST",
    body: JSON.stringify({ csv: importCsvText, dry_run: dryRun })
  });
  const data = await readJson(response);
  if (!response.ok) {
    importResult.innerHTML = `<div class="import-summary has-errors">${escapeHtml(
      getErrorMessage(data, t("import.failed"))
    )}</div>`;
    return null;
  }
  renderImportResult(data);
  return data;
}

importFile.addEventListener("change", async () => {
  const file = importFile.files[0];
  if (!file) return;

  $("importFileName").textContent = file.name;
  importResult.innerHTML = `<div class="metric-note">${escapeHtml(t("import.checking"))}</div>`;
  confirmImportBtn.disabled = true;

  try {
    importCsvText = await file.text();
    // A dry run first, so the user sees what will happen before anything is saved.
    const preview = await runImport(true);
    confirmImportBtn.disabled = !preview || preview.errors.length > 0 || preview.created + preview.updated === 0;
  } catch (error) {
    console.error(error);
    importResult.innerHTML = `<div class="import-summary has-errors">${escapeHtml(t("import.failed"))}</div>`;
  }
});

confirmImportBtn.addEventListener("click", async () => {
  setButtonLoading(confirmImportBtn, true, t("common.saving"));
  try {
    const result = await runImport(false);
    if (result?.saved) {
      showToast(t("import.done"), "success");
      categories = await loadCategories();
      categoryFilter.innerHTML = categoryOptions(categories, null, t("common.allCategories"));
      formCategory.innerHTML = categoryOptions(categories);
      reloadFromFirstPage();
    }
  } finally {
    setButtonLoading(confirmImportBtn, false);
    confirmImportBtn.disabled = true;
  }
});

// ----- Modal plumbing -----

[stockModalOverlay, transferModalOverlay, historyModalOverlay, editModalOverlay, deleteModalOverlay, importModalOverlay].forEach(
  (overlay) => {
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay || e.target.closest("[data-close-modal]")) {
        closeModal(overlay);
      }
    });
  }
);

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    document.querySelectorAll(".modal-overlay.show").forEach(closeModal);
  }
});

currentUser = await initProtectedPage();

if (currentUser) {
  try {
    await loadLookups();
  } catch (error) {
    console.error(error);
    showToast(t("products.lookupsFailed"), "error");
  }
  reloadAll();
}
