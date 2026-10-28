import { apiFetch, readJson } from "./config.js?v=5";
import { initProtectedPage, isAdmin } from "./auth.js?v=5";
import {
  categoryOptions,
  formatQuantity,
  loadCategories,
  loadUnits,
  loadWarehouses,
  MOVEMENT_LABELS,
  optionalNumber,
  quantityStep,
  unitOptions,
  warehouseOptions
} from "./inventory.js?v=5";
import {
  escapeHtml,
  formatCurrency,
  formatDate,
  getErrorMessage,
  refreshIcons,
  renderEmptyRow,
  setButtonLoading,
  showToast
} from "./ui.js?v=5";

const productsTable = document.getElementById("productsTable");
const archivedProductsTable = document.getElementById("archivedProductsTable");
const productForm = document.getElementById("productForm");
const addProductButton = document.getElementById("addProductButton");
const productSearch = document.getElementById("productSearch");
const categoryFilter = document.getElementById("categoryFilter");
const lowStockFilter = document.getElementById("lowStockFilter");
const sortSelect = document.getElementById("sortSelect");

const formCategory = document.getElementById("category");
const formUnit = document.getElementById("unit");
const formWarehouse = document.getElementById("warehouse");
const formStock = document.getElementById("stock_quantity");
const formMinStock = document.getElementById("min_stock");

const stockModalOverlay = document.getElementById("stockModalOverlay");
const stockModalTitle = document.getElementById("stockModalTitle");
const stockModalSubtitle = document.getElementById("stockModalSubtitle");
const stockModalQuantity = document.getElementById("stockModalQuantity");
const stockModalWarehouse = document.getElementById("stockModalWarehouse");
const stockModalNote = document.getElementById("stockModalNote");
const confirmStockModalBtn = document.getElementById("confirmStockModalBtn");

const transferModalOverlay = document.getElementById("transferModalOverlay");
const transferModalSubtitle = document.getElementById("transferModalSubtitle");
const transferFrom = document.getElementById("transferFrom");
const transferTo = document.getElementById("transferTo");
const transferQuantity = document.getElementById("transferQuantity");
const transferNote = document.getElementById("transferNote");
const transferLevels = document.getElementById("transferLevels");
const confirmTransferBtn = document.getElementById("confirmTransferBtn");

const historyModalOverlay = document.getElementById("historyModalOverlay");
const historyModalSubtitle = document.getElementById("historyModalSubtitle");
const historyLevels = document.getElementById("historyLevels");
const historyTable = document.getElementById("historyTable");

const editModalOverlay = document.getElementById("editModalOverlay");
const editName = document.getElementById("editName");
const editBarcode = document.getElementById("editBarcode");
const editCategory = document.getElementById("editCategory");
const editUnit = document.getElementById("editUnit");
const editMinStock = document.getElementById("editMinStock");
const editPrice = document.getElementById("editPrice");
const saveEditModalBtn = document.getElementById("saveEditModalBtn");

const deleteModalOverlay = document.getElementById("deleteModalOverlay");
const confirmDeleteModalBtn = document.getElementById("confirmDeleteModalBtn");
const deleteModalText = document.getElementById("deleteModalText");

let currentUser = null;
let products = [];
let units = [];
let categories = [];
let warehouses = [];
let currentStockProduct = null;
let currentStockAction = null;
let currentTransferProduct = null;
let currentEditProductId = null;
let currentDeleteProductId = null;

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
  [units, categories, warehouses] = await Promise.all([loadUnits(), loadCategories(), loadWarehouses()]);

  formUnit.innerHTML = unitOptions(units);
  editUnit.innerHTML = unitOptions(units);
  formCategory.innerHTML = categoryOptions(categories);
  editCategory.innerHTML = categoryOptions(categories);
  categoryFilter.innerHTML = categoryOptions(categories, null, "All categories");

  const options = warehouseOptions(warehouses);
  formWarehouse.innerHTML = options;
  stockModalWarehouse.innerHTML = options;

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
editUnit.addEventListener("change", () => {
  editMinStock.step = quantityStep(units, editUnit.value);
});

// ----- Product list -----

function buildProductQuery() {
  const params = new URLSearchParams();
  const search = productSearch.value.trim();
  if (search) params.set("search", search);
  if (categoryFilter.value) params.set("category_id", categoryFilter.value);
  if (lowStockFilter.checked) params.set("low_stock", "true");
  if (sortSelect.value !== "id") params.set("sort", sortSelect.value);
  const query = params.toString();
  return query ? `?${query}` : "";
}

async function loadProducts() {
  try {
    const response = await apiFetch(`/products/${buildProductQuery()}`);
    const data = await readJson(response);

    if (!response.ok) {
      showToast(getErrorMessage(data, "Failed to load products"), "error");
      return;
    }

    products = data;
    renderProducts();
  } catch (error) {
    console.error(error);
    showToast("Request failed", "error");
  }
}

function renderProducts() {
  if (!products.length) {
    renderEmptyRow(productsTable, 7, "No products found.");
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
            product.min_stock === null ? "" : `Minimum: ${escapeHtml(formatQuantity(product.min_stock, product.unit))}`
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

function renderProductActions(productId) {
  const history = `
    <button class="btn btn-secondary icon-btn" data-action="history" data-id="${productId}">
      <i data-lucide="history"></i>
      <span>History</span>
    </button>
  `;

  if (!isAdmin(currentUser)) {
    return `<div class="row-actions">${history}</div>`;
  }

  return `
    <div class="row-actions">
      <button class="btn btn-secondary icon-btn" data-action="edit" data-id="${productId}">
        <i data-lucide="square-pen"></i>
        <span>Edit</span>
      </button>
      <button class="btn btn-secondary icon-btn" data-action="increase" data-id="${productId}">
        <i data-lucide="package-plus"></i>
        <span>Stock In</span>
      </button>
      <button class="btn btn-secondary icon-btn" data-action="decrease" data-id="${productId}">
        <i data-lucide="package-minus"></i>
        <span>Stock Out</span>
      </button>
      ${
        hasManyWarehouses()
          ? `<button class="btn btn-secondary icon-btn" data-action="transfer" data-id="${productId}">
              <i data-lucide="arrow-left-right"></i>
              <span>Transfer</span>
            </button>`
          : ""
      }
      ${history}
      <button class="btn btn-danger icon-btn" data-action="archive" data-id="${productId}">
        <i data-lucide="archive"></i>
        <span>Archive</span>
      </button>
    </div>
  `;
}

async function loadArchivedProducts() {
  try {
    const response = await apiFetch("/products/?status=archived");
    const archived = await readJson(response);

    if (!response.ok) {
      showToast(getErrorMessage(archived, "Failed to load archived products"), "error");
      return;
    }

    if (!archived.length) {
      renderEmptyRow(archivedProductsTable, 4, "No archived products.");
      return;
    }

    archivedProductsTable.innerHTML = archived
      .map(
        (product) => `
          <tr>
            <td>${escapeHtml(product.id)}</td>
            <td><strong>${escapeHtml(product.name)}</strong></td>
            <td>${escapeHtml(product.barcode)}</td>
            <td>
              <button class="btn btn-secondary icon-btn" data-action="restore" data-id="${product.id}">
                <i data-lucide="archive-restore"></i>
                <span>Restore</span>
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
    : `<div class="metric-note">No stock in any warehouse.</div>`;
}

// ----- Add product -----

productForm.addEventListener("submit", async (e) => {
  e.preventDefault();

  const payload = {
    name: document.getElementById("name").value.trim(),
    barcode: document.getElementById("barcode").value.trim(),
    category_id: optionalNumber(formCategory.value),
    unit: formUnit.value,
    stock_quantity: Number(formStock.value || 0),
    min_stock: optionalNumber(formMinStock.value),
    price: optionalNumber(document.getElementById("price").value)
  };
  if (hasManyWarehouses()) payload.warehouse_id = Number(formWarehouse.value);

  setButtonLoading(addProductButton, true, "Adding...");

  try {
    const created = await submitJson("/products/", "POST", payload, "Failed to add product");
    if (!created) return;

    showToast("Product added", "success");
    productForm.reset();
    formUnit.value = "pcs";
    syncFormSteps();
    loadProducts();
  } catch (error) {
    console.error(error);
    showToast("Request failed", "error");
  } finally {
    setButtonLoading(addProductButton, false);
  }
});

let searchTimer = null;
productSearch.addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(loadProducts, 250);
});
categoryFilter.addEventListener("change", loadProducts);
lowStockFilter.addEventListener("change", loadProducts);
sortSelect.addEventListener("change", loadProducts);

// ----- Modals -----

function openModal(overlay) {
  overlay.classList.add("show");
  const firstInput = overlay.querySelector("input");
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
  stockModalQuantity.value = "";
  stockModalQuantity.step = quantityStep(units, product.unit);
  stockModalNote.value = "";
  stockModalWarehouse.innerHTML = warehouseOptions(warehouses);
  stockModalTitle.textContent = action === "increase" ? "Stock In" : "Stock Out";
  stockModalSubtitle.textContent = `${product.name} · current: ${formatQuantity(product.stock_quantity, product.unit)}`;
  openModal(stockModalOverlay);
}

async function openTransferModal(productId) {
  const product = findProduct(productId);
  if (!product) return;

  currentTransferProduct = product;
  transferModalSubtitle.textContent = product.name;
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
  renderLevels(transferLevels, levels, product.unit);
  openModal(transferModalOverlay);
}

async function openHistoryModal(productId) {
  const product = findProduct(productId);
  if (!product) return;

  historyModalSubtitle.textContent = `${product.name} · ${formatQuantity(product.stock_quantity, product.unit)} in stock`;
  renderEmptyRow(historyTable, 7, "Loading...");
  historyLevels.innerHTML = "";
  openModal(historyModalOverlay);

  try {
    const [levels, response] = await Promise.all([
      fetchStockLevels(productId),
      apiFetch(`/products/${productId}/movements`)
    ]);
    const movements = await readJson(response);

    if (!response.ok) {
      renderEmptyRow(historyTable, 7, getErrorMessage(movements, "Failed to load history"));
      return;
    }

    renderLevels(historyLevels, levels, product.unit);

    if (!movements.length) {
      renderEmptyRow(historyTable, 7, "No stock movements yet.");
      return;
    }

    historyTable.innerHTML = movements
      .map(
        (movement) => `
          <tr>
            <td>${escapeHtml(formatDate(movement.created_at))}</td>
            <td>${escapeHtml(MOVEMENT_LABELS[movement.reason] || movement.reason)}</td>
            <td>${escapeHtml(movement.warehouse_name || "-")}</td>
            <td class="${movement.change < 0 ? "stock-low" : "stock-good"}">
              ${movement.change > 0 ? "+" : ""}${escapeHtml(formatQuantity(movement.change, product.unit))}
            </td>
            <td>${escapeHtml(formatQuantity(movement.quantity_after, product.unit))}</td>
            <td>${escapeHtml(movement.username || "-")}</td>
            <td>${escapeHtml(movement.note || "")}</td>
          </tr>
        `
      )
      .join("");
  } catch (error) {
    console.error(error);
    renderEmptyRow(historyTable, 7, "Request failed");
  }
}

function openEditModal(productId) {
  const product = findProduct(productId);
  if (!product) return;

  currentEditProductId = productId;
  editName.value = product.name;
  editBarcode.value = product.barcode;
  editCategory.innerHTML = categoryOptions(categories, product.category_id);
  editUnit.innerHTML = unitOptions(units, product.unit);
  editMinStock.value = product.min_stock ?? "";
  editMinStock.step = quantityStep(units, product.unit);
  editPrice.value = product.price ?? "";
  openModal(editModalOverlay);
}

function openDeleteModal(productId) {
  const product = findProduct(productId);
  if (!product) return;

  currentDeleteProductId = productId;
  deleteModalText.textContent = `Are you sure you want to archive "${product.name}"?`;
  openModal(deleteModalOverlay);
}

async function restoreProduct(productId) {
  try {
    const restored = await submitJson(`/products/${productId}/restore`, "POST", undefined, "Restore failed");
    if (!restored) return;

    showToast("Product restored", "success");
    reloadAll();
  } catch (error) {
    console.error(error);
    showToast("Request failed", "error");
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
    showToast("Enter a valid quantity", "error");
    return;
  }

  const payload = { quantity, note: stockModalNote.value };
  if (hasManyWarehouses()) payload.warehouse_id = Number(stockModalWarehouse.value);

  setButtonLoading(confirmStockModalBtn, true, "Saving...");

  try {
    const updated = await submitJson(
      `/products/${currentStockProduct.id}/${currentStockAction}-stock`,
      "POST",
      payload,
      "Stock update failed"
    );
    if (!updated) return;

    showToast("Stock updated", "success");
    closeModal(stockModalOverlay);
    loadProducts();
  } catch (error) {
    console.error(error);
    showToast("Request failed", "error");
  } finally {
    setButtonLoading(confirmStockModalBtn, false);
  }
});

confirmTransferBtn.addEventListener("click", async () => {
  const quantity = Number(transferQuantity.value);

  if (!quantity || quantity <= 0) {
    showToast("Enter a valid quantity", "error");
    return;
  }

  setButtonLoading(confirmTransferBtn, true, "Moving...");

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
      "Transfer failed"
    );
    if (!updated) return;

    showToast("Stock transferred", "success");
    closeModal(transferModalOverlay);
    loadProducts();
  } catch (error) {
    console.error(error);
    showToast("Request failed", "error");
  } finally {
    setButtonLoading(confirmTransferBtn, false);
  }
});

saveEditModalBtn.addEventListener("click", async () => {
  const payload = {
    name: editName.value.trim(),
    barcode: editBarcode.value.trim(),
    category_id: optionalNumber(editCategory.value),
    unit: editUnit.value,
    min_stock: optionalNumber(editMinStock.value),
    price: optionalNumber(editPrice.value)
  };

  setButtonLoading(saveEditModalBtn, true, "Saving...");

  try {
    const updated = await submitJson(`/products/${currentEditProductId}`, "PATCH", payload, "Update failed");
    if (!updated) return;

    showToast("Product updated", "success");
    closeModal(editModalOverlay);
    loadProducts();
  } catch (error) {
    console.error(error);
    showToast("Request failed", "error");
  } finally {
    setButtonLoading(saveEditModalBtn, false);
  }
});

confirmDeleteModalBtn.addEventListener("click", async () => {
  setButtonLoading(confirmDeleteModalBtn, true, "Archiving...");

  try {
    const result = await submitJson(`/products/${currentDeleteProductId}`, "DELETE", undefined, "Archive failed");
    if (!result) return;

    showToast("Product archived", "success");
    closeModal(deleteModalOverlay);
    reloadAll();
  } catch (error) {
    console.error(error);
    showToast("Request failed", "error");
  } finally {
    setButtonLoading(confirmDeleteModalBtn, false);
  }
});

[stockModalOverlay, transferModalOverlay, historyModalOverlay, editModalOverlay, deleteModalOverlay].forEach(
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
    showToast("Failed to load categories and warehouses", "error");
  }
  reloadAll();
}
