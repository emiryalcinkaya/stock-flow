import { apiFetch, readJson } from "./config.js";
import { initProtectedPage, isAdmin } from "./auth.js";
import { escapeHtml, getErrorMessage, refreshIcons, renderEmptyRow, showToast } from "./ui.js";

const categoryForm = document.getElementById("categoryForm");
const categoryName = document.getElementById("categoryName");
const categoriesTable = document.getElementById("categoriesTable");
const warehouseForm = document.getElementById("warehouseForm");
const warehouseName = document.getElementById("warehouseName");
const warehousesTable = document.getElementById("warehousesTable");

async function request(endpoint, method = "GET", body) {
  const response = await apiFetch(endpoint, {
    method,
    body: body === undefined ? undefined : JSON.stringify(body)
  });
  const data = await readJson(response);
  if (!response.ok) {
    showToast(getErrorMessage(data, "Request failed"), "error");
    return null;
  }
  return data;
}

// ----- Categories -----

async function loadCategories() {
  const categories = await request("/categories");
  if (!categories) return;

  if (!categories.length) {
    renderEmptyRow(categoriesTable, 3, "No categories yet.");
    return;
  }

  categoriesTable.innerHTML = categories
    .map(
      (category) => `
        <tr>
          <td><strong>${escapeHtml(category.name)}</strong></td>
          <td>${escapeHtml(category.product_count)}</td>
          <td>
            <div class="row-actions">
              <button class="btn btn-secondary icon-btn" data-action="rename-category" data-id="${category.id}"
                data-name="${escapeHtml(category.name)}">
                <i data-lucide="square-pen"></i>
                <span>Rename</span>
              </button>
              <button class="btn btn-danger icon-btn" data-action="delete-category" data-id="${category.id}"
                data-name="${escapeHtml(category.name)}">
                <i data-lucide="trash-2"></i>
                <span>Delete</span>
              </button>
            </div>
          </td>
        </tr>
      `
    )
    .join("");

  refreshIcons();
}

categoryForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const created = await request("/categories", "POST", { name: categoryName.value });
  if (!created) return;

  showToast("Category added", "success");
  categoryForm.reset();
  loadCategories();
});

// ----- Warehouses -----

async function loadWarehouses() {
  const warehouses = await request("/warehouses?include_inactive=true");
  if (!warehouses) return;

  warehousesTable.innerHTML = warehouses
    .map(
      (warehouse) => `
        <tr>
          <td>
            <strong>${escapeHtml(warehouse.name)}</strong>
            ${warehouse.is_default ? `<span class="status-badge status-completed">default</span>` : ""}
          </td>
          <td>${escapeHtml(warehouse.product_count)}</td>
          <td>${warehouse.is_active ? "Active" : "Inactive"}</td>
          <td>
            <div class="row-actions">
              <button class="btn btn-secondary icon-btn" data-action="rename-warehouse" data-id="${warehouse.id}"
                data-name="${escapeHtml(warehouse.name)}">
                <i data-lucide="square-pen"></i>
                <span>Rename</span>
              </button>
              ${
                warehouse.is_active && !warehouse.is_default
                  ? `<button class="btn btn-secondary icon-btn" data-action="default-warehouse" data-id="${warehouse.id}">
                      <i data-lucide="star"></i>
                      <span>Make Default</span>
                    </button>
                    <button class="btn btn-danger icon-btn" data-action="deactivate-warehouse" data-id="${warehouse.id}">
                      <i data-lucide="archive"></i>
                      <span>Deactivate</span>
                    </button>`
                  : ""
              }
              ${
                !warehouse.is_active
                  ? `<button class="btn btn-secondary icon-btn" data-action="activate-warehouse" data-id="${warehouse.id}">
                      <i data-lucide="archive-restore"></i>
                      <span>Activate</span>
                    </button>`
                  : ""
              }
            </div>
          </td>
        </tr>
      `
    )
    .join("");

  refreshIcons();
}

warehouseForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const created = await request("/warehouses", "POST", { name: warehouseName.value });
  if (!created) return;

  showToast("Warehouse added", "success");
  warehouseForm.reset();
  loadWarehouses();
});

// ----- Row actions -----

async function renameCategory(id, currentName) {
  const name = window.prompt("New category name", currentName);
  if (!name || name.trim() === currentName) return;
  if (await request(`/categories/${id}`, "PATCH", { name })) {
    showToast("Category renamed", "success");
    loadCategories();
  }
}

async function deleteCategory(id, name) {
  if (!window.confirm(`Delete category "${name}"? Its products will become uncategorized.`)) return;
  if (await request(`/categories/${id}`, "DELETE")) {
    showToast("Category deleted", "success");
    loadCategories();
  }
}

async function updateWarehouse(id, changes, message) {
  if (await request(`/warehouses/${id}`, "PATCH", changes)) {
    showToast(message, "success");
    loadWarehouses();
  }
}

async function renameWarehouse(id, currentName) {
  const name = window.prompt("New warehouse name", currentName);
  if (!name || name.trim() === currentName) return;
  updateWarehouse(id, { name }, "Warehouse renamed");
}

const actions = {
  "rename-category": (button) => renameCategory(Number(button.dataset.id), button.dataset.name),
  "delete-category": (button) => deleteCategory(Number(button.dataset.id), button.dataset.name),
  "rename-warehouse": (button) => renameWarehouse(Number(button.dataset.id), button.dataset.name),
  "default-warehouse": (button) =>
    updateWarehouse(Number(button.dataset.id), { is_default: true }, "Default warehouse changed"),
  "deactivate-warehouse": (button) =>
    updateWarehouse(Number(button.dataset.id), { is_active: false }, "Warehouse deactivated"),
  "activate-warehouse": (button) =>
    updateWarehouse(Number(button.dataset.id), { is_active: true }, "Warehouse activated")
};

document.addEventListener("click", (e) => {
  const button = e.target.closest("[data-action]");
  if (!button) return;

  const handler = actions[button.dataset.action];
  if (handler) handler(button);
});

const currentUser = await initProtectedPage();

if (currentUser && !isAdmin(currentUser)) {
  window.location.replace("dashboard.html");
} else if (currentUser) {
  loadCategories();
  loadWarehouses();
}
