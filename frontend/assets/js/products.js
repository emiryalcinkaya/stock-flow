import { apiFetch, readJson } from "./config.js";
import { initProtectedPage, isAdmin } from "./auth.js";
import {
  escapeHtml,
  formatCurrency,
  getErrorMessage,
  refreshIcons,
  renderEmptyRow,
  setButtonLoading,
  showToast
} from "./ui.js";

const productsTable = document.getElementById("productsTable");
const archivedProductsTable = document.getElementById("archivedProductsTable");
const productForm = document.getElementById("productForm");
const addProductButton = document.getElementById("addProductButton");
const productSearch = document.getElementById("productSearch");

const stockModalOverlay = document.getElementById("stockModalOverlay");
const stockModalTitle = document.getElementById("stockModalTitle");
const stockModalQuantity = document.getElementById("stockModalQuantity");
const confirmStockModalBtn = document.getElementById("confirmStockModalBtn");

const editModalOverlay = document.getElementById("editModalOverlay");
const editName = document.getElementById("editName");
const editBarcode = document.getElementById("editBarcode");
const editPrice = document.getElementById("editPrice");
const editStock = document.getElementById("editStock");
const saveEditModalBtn = document.getElementById("saveEditModalBtn");

const deleteModalOverlay = document.getElementById("deleteModalOverlay");
const confirmDeleteModalBtn = document.getElementById("confirmDeleteModalBtn");
const deleteModalText = document.getElementById("deleteModalText");

let currentUser = null;
let products = [];
let lowStockThreshold = 5;
let currentStockProductId = null;
let currentStockAction = null;
let currentEditProductId = null;
let currentDeleteProductId = null;

function findProduct(id) {
  return products.find((product) => product.id === id);
}

async function loadLowStockThreshold() {
  const response = await apiFetch("/dashboard/summary");
  if (response.ok) {
    const summary = await readJson(response);
    lowStockThreshold = summary.low_stock_threshold;
  }
}

async function loadProducts() {
  try {
    const search = productSearch.value.trim();
    const query = search ? `?search=${encodeURIComponent(search)}` : "";
    const response = await apiFetch(`/products/${query}`);
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
  const admin = isAdmin(currentUser);
  const columnCount = admin ? 6 : 5;

  if (!products.length) {
    renderEmptyRow(productsTable, columnCount, "No active products found.");
    return;
  }

  productsTable.innerHTML = products
    .map(
      (product) => `
        <tr>
          <td>${escapeHtml(product.id)}</td>
          <td><strong>${escapeHtml(product.name)}</strong></td>
          <td>${escapeHtml(product.barcode)}</td>
          <td>${formatCurrency(product.price)}</td>
          <td class="${product.stock_quantity < lowStockThreshold ? "stock-low" : "stock-good"}">
            ${escapeHtml(product.stock_quantity)}
          </td>
          ${admin ? renderProductActions(product.id) : ""}
        </tr>
      `
    )
    .join("");

  refreshIcons();
}

function renderProductActions(productId) {
  return `
    <td>
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
        <button class="btn btn-danger icon-btn" data-action="archive" data-id="${productId}">
          <i data-lucide="archive"></i>
          <span>Archive</span>
        </button>
      </div>
    </td>
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

productForm.addEventListener("submit", async (e) => {
  e.preventDefault();

  const payload = {
    name: document.getElementById("name").value.trim(),
    barcode: document.getElementById("barcode").value.trim(),
    price: Number(document.getElementById("price").value),
    stock_quantity: Number(document.getElementById("stock_quantity").value)
  };

  setButtonLoading(addProductButton, true, "Adding...");

  try {
    const created = await submitJson("/products/", "POST", payload, "Failed to add product");
    if (!created) return;

    showToast("Product added", "success");
    productForm.reset();
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
  currentStockProductId = productId;
  currentStockAction = action;
  stockModalQuantity.value = "";
  stockModalTitle.textContent = action === "increase" ? "Increase Stock" : "Decrease Stock";
  openModal(stockModalOverlay);
}

function openEditModal(productId) {
  const product = findProduct(productId);
  if (!product) return;

  currentEditProductId = productId;
  editName.value = product.name;
  editBarcode.value = product.barcode;
  editPrice.value = product.price;
  editStock.value = product.stock_quantity;
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

  if (!Number.isInteger(quantity) || quantity <= 0) {
    showToast("Enter a valid quantity", "error");
    return;
  }

  setButtonLoading(confirmStockModalBtn, true, "Saving...");

  try {
    const updated = await submitJson(
      `/products/${currentStockProductId}/${currentStockAction}-stock`,
      "POST",
      { quantity },
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

saveEditModalBtn.addEventListener("click", async () => {
  const payload = {
    name: editName.value.trim(),
    barcode: editBarcode.value.trim(),
    price: Number(editPrice.value),
    stock_quantity: Number(editStock.value)
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

[stockModalOverlay, editModalOverlay, deleteModalOverlay].forEach((overlay) => {
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay || e.target.closest("[data-close-modal]")) {
      closeModal(overlay);
    }
  });
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    document.querySelectorAll(".modal-overlay.show").forEach(closeModal);
  }
});

currentUser = await initProtectedPage();

if (currentUser) {
  await loadLowStockThreshold();
  reloadAll();
}
