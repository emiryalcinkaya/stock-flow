import { apiFetch, readJson } from "./config.js?v=9";
import { initProtectedPage, languageOptions } from "./auth.js?v=9";
import { setLanguage, t } from "./i18n.js?v=9";
import { escapeHtml, getErrorMessage, refreshIcons, renderEmptyRow, setCurrency, showToast } from "./ui.js?v=9";

const $ = (id) => document.getElementById(id);

async function request(endpoint, method = "GET", body) {
  const response = await apiFetch(endpoint, {
    method,
    body: body === undefined ? undefined : JSON.stringify(body)
  });
  const data = await readJson(response);
  if (!response.ok) {
    showToast(getErrorMessage(data, t("common.requestFailed")), "error");
    return null;
  }
  return data;
}

function rowButton(action, id, icon, labelKey, { danger = false, name = "" } = {}) {
  return `
    <button class="btn ${danger ? "btn-danger" : "btn-secondary"} icon-btn" data-action="${action}" data-id="${id}"
      data-name="${escapeHtml(name)}">
      <i data-lucide="${icon}"></i>
      <span>${escapeHtml(t(labelKey))}</span>
    </button>
  `;
}

function activeBadge(isActive) {
  return `<span class="status-badge ${isActive ? "status-completed" : "status-cancelled"}">${escapeHtml(
    t(isActive ? "common.active" : "common.inactive")
  )}</span>`;
}

// ----- Business -----

const DEFAULT_LOGO = "assets/images/logo.svg";
const MAX_LOGO_SIDE = 256;
const MAX_LOGO_BYTES = 300 * 1024;

const companyLogoInput = $("companyLogoInput");
const companyLogoPreview = $("companyLogoPreview");
const removeLogoButton = $("removeLogoButton");
const saveCompanyButton = $("saveCompanyButton");

// null = no logo (Eysto's is shown instead); a data URL = the business logo.
let companyLogo = null;

function showLogo() {
  companyLogoPreview.src = companyLogo || DEFAULT_LOGO;
  removeLogoButton.hidden = !companyLogo;
}

function readAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

// Photos can be several MB; shrink them to a small PNG before sending.
async function toLogoDataUrl(file) {
  const dataUrl = await readAsDataUrl(file);
  if (file.type === "image/svg+xml") return dataUrl;

  // onload instead of image.decode(): decode() can hang in some browsers.
  const image = await new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("Unreadable image"));
    img.src = dataUrl;
  });

  const scale = Math.min(1, MAX_LOGO_SIDE / Math.max(image.width, image.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(image.width * scale);
  canvas.height = Math.round(image.height * scale);
  canvas.getContext("2d").drawImage(image, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL("image/png");
}

async function loadCompany() {
  const company = await request("/company");
  if (!company) return;

  $("companyName").value = company.name || "";
  $("companyDescription").value = company.description || "";
  $("companyCurrency").value = company.currency || "USD";
  companyLogo = company.logo;
  showLogo();
}

companyLogoInput.addEventListener("change", async () => {
  const file = companyLogoInput.files[0];
  companyLogoInput.value = "";
  if (!file) return;

  // Saving while the image is still being processed would drop the new logo.
  saveCompanyButton.disabled = true;

  try {
    const dataUrl = await toLogoDataUrl(file);
    // Base64 is ~4/3 of the binary size.
    if (dataUrl.length * 0.75 > MAX_LOGO_BYTES) {
      showToast(t("settings.logoTooLarge"), "error");
      return;
    }
    companyLogo = dataUrl;
    showLogo();
  } catch (error) {
    console.error(error);
    showToast(t("settings.logoUnreadable"), "error");
  } finally {
    saveCompanyButton.disabled = false;
  }
});

removeLogoButton.addEventListener("click", () => {
  companyLogo = null;
  showLogo();
});

$("companyForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  saveCompanyButton.disabled = true;

  const saved = await request("/company", "PATCH", {
    name: $("companyName").value,
    description: $("companyDescription").value,
    currency: $("companyCurrency").value,
    logo: companyLogo
  });

  saveCompanyButton.disabled = false;
  if (saved) {
    setCurrency(saved.currency);
    showToast(t("settings.businessSaved"), "success");
  }
});

// ----- Categories -----

async function loadCategories() {
  const categories = await request("/categories");
  if (!categories) return;

  if (!categories.length) {
    renderEmptyRow($("categoriesTable"), 3, t("settings.noCategories"));
    return;
  }

  $("categoriesTable").innerHTML = categories
    .map(
      (category) => `
        <tr>
          <td><strong>${escapeHtml(category.name)}</strong></td>
          <td>${escapeHtml(category.product_count)}</td>
          <td>
            <div class="row-actions">
              ${rowButton("rename-category", category.id, "square-pen", "action.rename", { name: category.name })}
              ${rowButton("delete-category", category.id, "trash-2", "action.delete", { danger: true, name: category.name })}
            </div>
          </td>
        </tr>
      `
    )
    .join("");

  refreshIcons();
}

$("categoryForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const created = await request("/categories", "POST", { name: $("categoryName").value });
  if (!created) return;

  showToast(t("settings.categoryAdded"), "success");
  $("categoryForm").reset();
  loadCategories();
});

// ----- Warehouses -----

async function loadWarehouses() {
  const warehouses = await request("/warehouses?include_inactive=true");
  if (!warehouses) return;

  $("warehousesTable").innerHTML = warehouses
    .map(
      (warehouse) => `
        <tr>
          <td>
            <strong>${escapeHtml(warehouse.name)}</strong>
            ${warehouse.is_default ? `<span class="status-badge status-completed">${escapeHtml(t("common.default"))}</span>` : ""}
          </td>
          <td>${escapeHtml(warehouse.product_count)}</td>
          <td>${activeBadge(warehouse.is_active)}</td>
          <td>
            <div class="row-actions">
              ${rowButton("rename-warehouse", warehouse.id, "square-pen", "action.rename", { name: warehouse.name })}
              ${
                warehouse.is_active && !warehouse.is_default
                  ? rowButton("default-warehouse", warehouse.id, "star", "settings.makeDefault") +
                    rowButton("deactivate-warehouse", warehouse.id, "archive", "users.deactivate", { danger: true })
                  : ""
              }
              ${!warehouse.is_active ? rowButton("activate-warehouse", warehouse.id, "archive-restore", "users.activate") : ""}
            </div>
          </td>
        </tr>
      `
    )
    .join("");

  refreshIcons();
}

$("warehouseForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const created = await request("/warehouses", "POST", { name: $("warehouseName").value });
  if (!created) return;

  showToast(t("settings.warehouseAdded"), "success");
  $("warehouseForm").reset();
  loadWarehouses();
});

// ----- Suppliers -----

async function loadSuppliers() {
  const suppliers = await request("/suppliers?include_inactive=true");
  if (!suppliers) return;

  if (!suppliers.length) {
    renderEmptyRow($("suppliersTable"), 6, t("settings.noSuppliers"));
    return;
  }

  $("suppliersTable").innerHTML = suppliers
    .map(
      (supplier) => `
        <tr>
          <td><strong>${escapeHtml(supplier.name)}</strong></td>
          <td>${escapeHtml(supplier.contact_name || "-")}</td>
          <td>${escapeHtml(supplier.phone || "-")}</td>
          <td>${escapeHtml(supplier.email || "-")}</td>
          <td>${activeBadge(supplier.is_active)}</td>
          <td>
            <div class="row-actions">
              ${rowButton("rename-supplier", supplier.id, "square-pen", "action.rename", { name: supplier.name })}
              ${
                supplier.is_active
                  ? rowButton("deactivate-supplier", supplier.id, "archive", "users.deactivate", { danger: true })
                  : rowButton("activate-supplier", supplier.id, "archive-restore", "users.activate")
              }
            </div>
          </td>
        </tr>
      `
    )
    .join("");

  refreshIcons();
}

$("supplierForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const created = await request("/suppliers", "POST", {
    name: $("supplierName").value,
    contact_name: $("supplierContact").value,
    phone: $("supplierPhone").value,
    email: $("supplierEmail").value
  });
  if (!created) return;

  showToast(t("settings.supplierAdded"), "success");
  $("supplierForm").reset();
  loadSuppliers();
});

// ----- Row actions -----

async function rename(endpoint, currentName, reload) {
  const name = window.prompt(t("settings.newName"), currentName);
  if (!name || name.trim() === currentName) return;
  if (await request(endpoint, "PATCH", { name })) {
    showToast(t("settings.renamed"), "success");
    reload();
  }
}

async function update(endpoint, changes, messageKey, reload) {
  if (await request(endpoint, "PATCH", changes)) {
    showToast(t(messageKey), "success");
    reload();
  }
}

const actions = {
  "rename-category": (id, name) => rename(`/categories/${id}`, name, loadCategories),
  "delete-category": async (id, name) => {
    if (!window.confirm(t("settings.deleteCategoryConfirm", { name }))) return;
    if (await request(`/categories/${id}`, "DELETE")) {
      showToast(t("settings.categoryDeleted"), "success");
      loadCategories();
    }
  },
  "rename-warehouse": (id, name) => rename(`/warehouses/${id}`, name, loadWarehouses),
  "default-warehouse": (id) => update(`/warehouses/${id}`, { is_default: true }, "settings.defaultChanged", loadWarehouses),
  "deactivate-warehouse": (id) => update(`/warehouses/${id}`, { is_active: false }, "users.deactivated", loadWarehouses),
  "activate-warehouse": (id) => update(`/warehouses/${id}`, { is_active: true }, "users.activated", loadWarehouses),
  "rename-supplier": (id, name) => rename(`/suppliers/${id}`, name, loadSuppliers),
  "deactivate-supplier": (id) => update(`/suppliers/${id}`, { is_active: false }, "users.deactivated", loadSuppliers),
  "activate-supplier": (id) => update(`/suppliers/${id}`, { is_active: true }, "users.activated", loadSuppliers)
};

document.addEventListener("click", (e) => {
  const button = e.target.closest("[data-action]");
  if (!button) return;

  const handler = actions[button.dataset.action];
  if (handler) handler(Number(button.dataset.id), button.dataset.name);
});

// ----- Users -----

let currentUser = null;
let users = [];
let editingUser = null;

async function loadUsers() {
  const data = await request("/users");
  if (!data) return;
  users = data;

  $("usersTable").innerHTML = users
    .map((user) => {
      const isSelf = user.id === currentUser.id;
      return `
        <tr>
          <td><strong>${escapeHtml(user.full_name)}</strong>${
            isSelf ? ` <span class="metric-note">(${escapeHtml(t("users.you"))})</span>` : ""
          }</td>
          <td>${escapeHtml(user.username)}</td>
          <td>${escapeHtml(user.email)}</td>
          <td>${escapeHtml(t(`role.${user.role}`))}</td>
          <td>${activeBadge(user.is_active)}</td>
          <td>
            <div class="row-actions">
              <button class="btn btn-secondary icon-btn" data-edit-user="${user.id}">
                <i data-lucide="square-pen"></i>
                <span>${escapeHtml(t("action.edit"))}</span>
              </button>
              ${
                isSelf
                  ? ""
                  : `<button class="btn ${user.is_active ? "btn-danger" : "btn-secondary"} icon-btn" data-toggle-user="${user.id}">
                      <i data-lucide="${user.is_active ? "user-x" : "user-check"}"></i>
                      <span>${escapeHtml(t(user.is_active ? "users.deactivate" : "users.activate"))}</span>
                    </button>`
              }
            </div>
          </td>
        </tr>
      `;
    })
    .join("");
  refreshIcons();
}

$("userForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const button = $("addUserButton");
  button.disabled = true;

  const created = await request("/users", "POST", {
    full_name: $("fullName").value,
    username: $("username").value.trim(),
    email: $("email").value.trim(),
    role: $("role").value,
    password: $("password").value
  });

  button.disabled = false;
  if (!created) return;

  showToast(t("users.added", { name: created.full_name }), "success");
  $("userForm").reset();
  loadUsers();
});

function openUserEdit(userId) {
  editingUser = users.find((user) => user.id === userId);
  if (!editingUser) return;

  $("editUserSubtitle").textContent = `${editingUser.full_name} · ${editingUser.username}`;
  $("editFullName").value = editingUser.full_name;
  $("editEmail").value = editingUser.email;
  $("editRole").value = editingUser.role;
  // Changing your own role could lock you out; the API refuses it anyway.
  $("editRole").disabled = editingUser.id === currentUser.id;
  $("editNewPassword").value = "";
  $("editUserOverlay").classList.add("show");
}

function closeUserEdit() {
  $("editUserOverlay").classList.remove("show");
}

$("saveUserButton").addEventListener("click", async (e) => {
  const button = e.currentTarget;
  const newPassword = $("editNewPassword").value;
  if (newPassword && newPassword.length < 8) {
    showToast(t("users.passwordTooShort"), "error");
    return;
  }

  button.disabled = true;
  try {
    const changes = { full_name: $("editFullName").value, email: $("editEmail").value.trim() };
    if (editingUser.id !== currentUser.id) changes.role = $("editRole").value;

    if (!(await request(`/users/${editingUser.id}`, "PATCH", changes))) return;
    if (newPassword && !(await request(`/users/${editingUser.id}/reset-password`, "POST", { new_password: newPassword }))) {
      return;
    }

    showToast(t("users.saved"), "success");
    closeUserEdit();
    loadUsers();
  } finally {
    button.disabled = false;
  }
});

$("usersTable").addEventListener("click", async (e) => {
  const edit = e.target.closest("[data-edit-user]");
  if (edit) {
    openUserEdit(Number(edit.dataset.editUser));
    return;
  }

  const toggle = e.target.closest("[data-toggle-user]");
  if (!toggle) return;
  const user = users.find((u) => u.id === Number(toggle.dataset.toggleUser));
  const activate = !user.is_active;
  if (!activate && !window.confirm(t("users.deactivateConfirm", { name: user.full_name }))) return;

  if (await request(`/users/${user.id}`, "PATCH", { is_active: activate })) {
    showToast(t(activate ? "users.activated" : "users.deactivated"), "success");
    loadUsers();
  }
});

$("editUserOverlay").addEventListener("click", (e) => {
  if (e.target.id === "editUserOverlay" || e.target.closest("[data-close-modal]")) closeUserEdit();
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeUserEdit();
});

currentUser = await initProtectedPage({ adminOnly: true });

if (currentUser) {
  $("languageSelect").innerHTML = languageOptions();
  $("languageSelect").addEventListener("change", () => {
    setLanguage($("languageSelect").value);
    // The sidebar and every label are rendered with the language, so start over.
    window.location.reload();
  });

  loadCompany();
  loadCategories();
  loadWarehouses();
  loadSuppliers();
  loadUsers();
}
