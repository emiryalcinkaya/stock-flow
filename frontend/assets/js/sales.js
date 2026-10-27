import { apiFetch, readJson } from "./config.js";
import { initProtectedPage } from "./auth.js";
import {
  escapeHtml,
  formatCurrency,
  getErrorMessage,
  refreshIcons,
  renderEmptyState,
  setButtonLoading,
  showToast
} from "./ui.js";

const productSelect = document.getElementById("productSelect");
const cartTable = document.getElementById("cartTable");
const cartTotal = document.getElementById("cartTotal");
const cartEmptyZone = document.querySelector(".cart-empty-zone");
const addToCartButton = document.getElementById("addToCartButton");
const submitSaleButton = document.getElementById("submitSaleButton");
const availableProductsList = document.getElementById("availableProductsList");

const saleQtyValue = document.getElementById("saleQtyValue");
const decreaseQtyBtn = document.getElementById("decreaseQtyBtn");
const increaseQtyBtn = document.getElementById("increaseQtyBtn");

let products = [];
let cart = [];
let selectedQuantity = 1;

function getSelectedProduct() {
  const productId = Number(productSelect.value);
  return products.find((product) => product.id === productId);
}

// Units of the selected product that are not already in the cart.
function remainingStock(product) {
  if (!product) return 0;
  const inCart = cart.find((item) => item.product_id === product.id);
  return product.stock_quantity - (inCart ? inCart.quantity : 0);
}

function updateQuantityUI() {
  const max = Math.max(1, remainingStock(getSelectedProduct()));
  if (selectedQuantity > max) selectedQuantity = max;

  saleQtyValue.textContent = selectedQuantity;
  decreaseQtyBtn.disabled = selectedQuantity <= 1;
  increaseQtyBtn.disabled = selectedQuantity >= max;
}

decreaseQtyBtn.addEventListener("click", () => {
  if (selectedQuantity > 1) {
    selectedQuantity--;
    updateQuantityUI();
  }
});

increaseQtyBtn.addEventListener("click", () => {
  selectedQuantity++;
  updateQuantityUI();
});

productSelect.addEventListener("change", () => {
  selectedQuantity = 1;
  updateQuantityUI();
});

async function loadProducts() {
  try {
    const response = await apiFetch("/products/");
    const data = await readJson(response);

    if (!response.ok) {
      showToast(getErrorMessage(data, "Failed to load products"), "error");
      return;
    }

    products = data;
    const availableProducts = products.filter((product) => product.stock_quantity > 0);

    productSelect.innerHTML = availableProducts.length
      ? availableProducts
          .map(
            (product) => `
              <option value="${product.id}">
                ${escapeHtml(product.name)} — ${formatCurrency(product.price)} — Stock: ${escapeHtml(product.stock_quantity)}
              </option>
            `
          )
          .join("")
      : `<option value="">No products available</option>`;

    renderAvailableProducts(availableProducts);
    updateQuantityUI();
  } catch (error) {
    console.error(error);
    showToast("Failed to load products", "error");
  }
}

function renderAvailableProducts(productList) {
  if (!productList.length) {
    renderEmptyState(availableProductsList, "No available products.");
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
              <div class="product-price">${formatCurrency(product.price)}</div>
            </div>
          </div>
          <div class="stock-pill">Stock: ${escapeHtml(product.stock_quantity)}</div>
        </div>
      `
    )
    .join("");

  refreshIcons();
}

addToCartButton.addEventListener("click", () => {
  const product = getSelectedProduct();
  const quantity = selectedQuantity;

  if (!product || quantity <= 0) {
    showToast("Select a valid product and quantity", "error");
    return;
  }

  if (quantity > remainingStock(product)) {
    showToast("Not enough stock", "error");
    return;
  }

  const existing = cart.find((item) => item.product_id === product.id);

  if (existing) {
    existing.quantity += quantity;
  } else {
    cart.push({
      product_id: product.id,
      product_name: product.name,
      quantity,
      unit_price: Number(product.price)
    });
  }

  selectedQuantity = 1;
  renderCart();
  updateQuantityUI();
  showToast("Item added to cart", "success");
});

function renderCart() {
  if (!cart.length) {
    cartTable.innerHTML = "";
    cartEmptyZone.innerHTML = `<div class="empty-state">Your cart is empty.</div>`;
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
          <td>${escapeHtml(item.quantity)}</td>
          <td>${formatCurrency(item.unit_price)}</td>
          <td>${formatCurrency(item.unit_price * item.quantity)}</td>
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
  const total = cart.reduce((sum, item) => sum + item.unit_price * item.quantity, 0);
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
    showToast("Cart is empty", "error");
    return;
  }

  setButtonLoading(submitSaleButton, true, "Creating...");

  try {
    const response = await apiFetch("/sales/", {
      method: "POST",
      body: JSON.stringify({
        items: cart.map((item) => ({
          product_id: item.product_id,
          quantity: item.quantity
        }))
      })
    });

    const data = await readJson(response);

    if (!response.ok) {
      showToast(getErrorMessage(data, "Sale creation failed"), "error");
      // Stock may have changed since the page loaded.
      loadProducts();
      return;
    }

    showToast(`Sale #${data.id} created`, "success");
    cart = [];
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
  renderCart();
  updateQuantityUI();
  loadProducts();
}
