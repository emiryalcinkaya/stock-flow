import { apiFetch, readJson } from "./config.js?v=6";
import { initProtectedPage } from "./auth.js?v=6";
import { t } from "./i18n.js?v=6";
import { escapeHtml, getErrorMessage, refreshIcons, setButtonLoading, showToast } from "./ui.js?v=6";

const $ = (id) => document.getElementById(id);

let currentUser = null;
let users = [];
let editingUser = null;

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
          <td><span class="status-badge ${user.is_active ? "status-completed" : "status-cancelled"}">${escapeHtml(
            t(user.is_active ? "common.active" : "common.inactive")
          )}</span></td>
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
  setButtonLoading(button, true, t("common.saving"));

  const created = await request("/users", "POST", {
    full_name: $("fullName").value,
    username: $("username").value.trim(),
    email: $("email").value.trim(),
    role: $("role").value,
    password: $("password").value
  });

  setButtonLoading(button, false);
  if (!created) return;

  showToast(t("users.added", { name: created.full_name }), "success");
  $("userForm").reset();
  loadUsers();
});

function openEdit(userId) {
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

function closeEdit() {
  $("editUserOverlay").classList.remove("show");
}

$("saveUserButton").addEventListener("click", async (e) => {
  const button = e.currentTarget;
  const newPassword = $("editNewPassword").value;
  if (newPassword && newPassword.length < 8) {
    showToast(t("users.passwordTooShort"), "error");
    return;
  }

  setButtonLoading(button, true, t("common.saving"));
  try {
    const changes = { full_name: $("editFullName").value, email: $("editEmail").value.trim() };
    if (editingUser.id !== currentUser.id) changes.role = $("editRole").value;

    const updated = await request(`/users/${editingUser.id}`, "PATCH", changes);
    if (!updated) return;

    if (newPassword) {
      const reset = await request(`/users/${editingUser.id}/reset-password`, "POST", { new_password: newPassword });
      if (!reset) return;
    }

    showToast(t("users.saved"), "success");
    closeEdit();
    loadUsers();
  } finally {
    setButtonLoading(button, false);
  }
});

$("usersTable").addEventListener("click", async (e) => {
  const edit = e.target.closest("[data-edit-user]");
  if (edit) {
    openEdit(Number(edit.dataset.editUser));
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
  if (e.target.id === "editUserOverlay" || e.target.closest("[data-close-modal]")) closeEdit();
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeEdit();
});

currentUser = await initProtectedPage({ adminOnly: true });

if (currentUser) {
  loadUsers();
}
