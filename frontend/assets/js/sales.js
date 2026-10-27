import { apiFetch, readJson } from "./config.js";
import { initProtectedPage } from "./auth.js";
import {
  formatQuantity,
  isWholeUnit,
  loadUnits,
  loadWarehouses,
  loadWarehouseStock,
  quantityStep,
  STOCK_OUT_REASONS,
  warehouseOptions
} from "./inventory.js";
import {
  escapeHtml,
  formatCurrency,
  getErrorMessage,
  refreshIcons,
  renderEmptyState,
  setButtonLoading,
  showToast
} from "./ui.js";

const reasonSelect = document.getElementById("reasonSelect");
const warehouseSelect = document.getElementById("warehouseSelect");
const noteInput = document.getElementById("noteInput");
const productSelect = document.getElementById("productSelect");
const cartTable = document.getElementById("cartTable");
const cartTotal = document.getElementById("cartTotal");
const cartEmptyZone = document.querySelector(".cart-empty-zone");
const addToCartButton = document.getElementById("addToCartButton");
const submitSaleButton = document.getElementById("submitSaleButton");
const availableProductsList = document.getElementById("availableProductsList");

const quantityInput = document.getElementById("saleQtyValue");
const decreaseQtyBtn = document.getElementById("decreaseQtyBtn");
const increaseQtyBtn = document.getElementById("increaseQtyBtn");

let units = [];
let warehouses = [];
let products = [];
// product id -> quantity available in the selected warehouse
let warehouseStock = {};
let cart = [];

// Avoids float noise like 0.1 + 0.2 when adding decimal quantities.
const roundQuantity = (value) => Math.round(value * 1000) / 1000;

function selectedWarehouseId() {
  return Number(warehouseSelect.value) || warehouses.find((w) => w.is_default)?.id;
}

function getSelectedProduct() {
  const productId = Number(productSelect.value);
  return products.find((product) => product.id === productId);
}

// Quantity of a product in the selected warehouse that is not already in the list.
function remainingStock(product) {
  if (!product) return 0;
  const inCart = cart.find((item) => item.product_id === product.id);
  return roundQuantity((warehouseStock[product.id] || 0) - (inCart ? inCart.quantity : 0));
}

function currentQuantity() {
  return Number(quantityInput.value) || 0;
}

function updateQuantityUI() {
  const product = getSelectedProduct();
  const max = remainingStock(product);
  const step = product ? quantityStep(units, product.unit) : "1";

  quantityInput.step = step;
  quantityInput.max = String(max);
  if (product && isWholeUnit(units, product.unit)) {
    quantityInput.value = String(Math.max(1, Math.round(currentQuantity())));
  }
  if (currentQuantity() > max && max > 0) quantityInput.value = String(max);

  decreaseQtyBtn.disabled = currentQuantity() <= 1;
  increaseQtyBtn.disabled = currentQuantity() >= max;
}

decreaseQtyBtn.addEventListener("click", () => {
  quantityInput.value = String(Math.max(1, roundQuantity(currentQuantity() - 1)));
  updateQuantityUI();
});

increaseQtyBtn.addEventListener("click", () => {
  quantityInput.value = String(roundQuantity(currentQuantity() + 1));
  updateQuantityUI();
});

quantityInput.addEventListener("change", updateQuantityUI);

productSelect.addEventListener("change", () => {
  quantityInput.value = "1";
  updateQuantityUI();
});

warehouseSelect.addEventListener("change", () => {
  if (cart.length) {
    // Items were checked against the previous warehouse's stock.
    cart = [];
    renderCart();
    showToast("Item list cleared for the new warehouse", "info");
  }
  loadProducts();
});

async function loadLookups() {
  [units, warehouses] = await Promise.all([loadUnits(), loadWarehouses()]);

  reasonSelect.innerHTML = Object.entries(STOCK_OUT_REASONS)
    .map(([value, label]) => `<option value="${value}">${escapeHtml(label)}</option>`)
    .join("");

  warehouseSelect.innerHTML = warehouseOptions(warehouses);
  document.querySelectorAll("[data-multi-warehouse]").forEach((element) => {
    element.hidden = warehouses.length < 2;
  });
}

async function loadProducts() {
  try {
    const [response, stock] = await Promise.all([
      apiFetch("/products/?limit=500"),
      loadWarehouseStock(selectedWarehouseId())
    ]);
    const data = await readJson(response);

    if (!response.ok) {
      showToast(getErrorMessage(data, "Failed to load products"), "error");
      return;
    }

    products = data;
    warehouseStock = stock;
    const availableProducts = products.filter((product) => (warehouseStock[product.id] || 0) > 0);

    productSelect.innerHTML = availableProducts.length
      ? availableProducts
          .map(
            (product) => `
              <option value="${product.id}">
                ${escapeHtml(product.name)} — In stock: ${escapeHtml(formatQuantity(warehouseStock[product.id], product.unit))}
              </option>
            `
          )
          .join("")
      : `<option value="">No products in stock</option>`;

    renderAvailableProducts(availableProducts);
    updateQuantityUI();
  } catch (error) {
    console.error(error);
    showToast("Failed to load products", "error");
  }
}

function renderAvailableProducts(productList) {
  if (!productList.length) {
    renderEmptyState(availableProductsList, "No products in stock.");
    return;
  }

  availableProductsList.innerHTML = productList
    .map(
      (product) => `
        <div class="soft-list-item">
          <div class="soft-list-left">
            <div class="product-icon">
              <i data-lucide="package"></i>
            </div>
            <div class="product-meta">
              <div class="product-name">${escapeHtml(product.name)}</div>
              <div class="product-price">${product.price === null ? "No price" : formatCurrency(product.price)}</div>
            </div>
          </div>
          <div class="stock-pill">${escapeHtml(formatQuantity(warehouseStock[product.id], product.unit))}</div>
        </div>
      `
    )
    .join("");

  refreshIcons();
}

addToCartButton.addEventListener("click", () => {
  const product = getSelectedProduct();
  const quantity = roundQuantity(currentQuantity());

  if (!product || quantity <= 0) {
    showToast("Select a valid product and quantity", "error");
    return;
  }

  if (isWholeUnit(units, product.unit) && !Number.isInteger(quantity)) {
    showToast(`${product.name} is counted in whole ${product.unit}`, "error");
    return;
  }

  if (quantity > remainingStock(product)) {
    showToast("Not enough stock in this warehouse", "error");
    return;
  }

  const existing = cart.find((item) => item.product_id === product.id);

  if (existing) {
    existing.quantity = roundQuantity(existing.quantity + quantity);
  } else {
    cart.push({
      product_id: product.id,
      product_name: product.name,
      unit: product.unit,
      quantity,
      unit_price: product.price === null ? null : Number(product.price)
    });
  }

  quantityInput.value = "1";
  renderCart();
  updateQuantityUI();
  showToast("Item added", "success");
});

function renderCart() {
  if (!cart.length) {
    cartTable.innerHTML = "";
    cartEmptyZone.innerHTML = `<div class="empty-state">No items yet.</div>`;
    cartTotal.textContent = formatCurrency(0);
    submitSaleButton.disabled = true;
    return;
  }

  cartEmptyZone.innerHTML = "";
  submitSaleButton.disabled = false;

  cartTable.innerHTML = cart
    .map(
      (item, index) => `
        <tr>
          <td>${escapeHtml(item.product_name)}</td>
          <td>${escapeHtml(formatQuantity(item.quantity, item.unit))}</td>
          <td>${item.unit_price === null ? "-" : formatCurrency(item.unit_price)}</td>
          <td>${item.unit_price === null ? "-" : formatCurrency(item.unit_price * item.quantity)}</td>
          <td>
            <button class="btn btn-danger icon-btn" data-remove-index="${index}">
              <i data-lucide="trash-2"></i>
              <span>Remove</span>
            </button>
          </td>
        </tr>
      `
    )
    .join("");

  // Display only: the server recalculates the total from current prices.
  const total = cart.reduce((sum, item) => sum + (item.unit_price || 0) * item.quantity, 0);
  cartTotal.textContent = formatCurrency(total);

  refreshIcons();
}

cartTable.addEventListener("click", (e) => {
  const button = e.target.closest("[data-remove-index]");
  if (!button) return;

  cart.splice(Number(button.dataset.removeIndex), 1);
  renderCart();
  updateQuantityUI();
});

submitSaleButton.addEventListener("click", async () => {
  if (!cart.length) {
    showToast("Add at least one item", "error");
    return;
  }

  setButtonLoading(submitSaleButton, true, "Saving...");

  const payload = {
    reason: reasonSelect.value,
    note: noteInput.value,
    items: cart.map((item) => ({
      product_id: item.product_id,
      quantity: item.quantity
    }))
  };
  if (warehouses.length > 1) payload.warehouse_id = selectedWarehouseId();

  try {
    const response = await apiFetch("/sales/", {
      method: "POST",
      body: JSON.stringify(payload)
    });

    const data = await readJson(response);

    if (!response.ok) {
      showToast(getErrorMessage(data, "Stock out failed"), "error");
      // Stock may have changed since the page loaded.
      loadProducts();
      return;
    }

    showToast(`Stock out #${data.id} recorded`, "success");
    cart = [];
    noteInput.value = "";
    loadProducts();
  } catch (error) {
    console.error(error);
    showToast("Request failed", "error");
  } finally {
    setButtonLoading(submitSaleButton, false);
    renderCart();
  }
});

if (await initProtectedPage()) {
  try {
    await loadLookups();
  } catch (error) {
    console.error(error);
    showToast("Failed to load warehouses", "error");
  }
  renderCart();
  loadProducts();
}
