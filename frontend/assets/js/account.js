import { apiFetch, readJson } from "./config.js?v=7";
import { initProtectedPage, languageOptions } from "./auth.js?v=7";
import { setLanguage, t } from "./i18n.js?v=7";
import { getErrorMessage, setButtonLoading, showToast } from "./ui.js?v=7";

const $ = (id) => document.getElementById(id);

const user = await initProtectedPage();

if (user) {
  $("accountSubtitle").textContent = `${user.full_name} · ${user.username} · ${t(`role.${user.role}`)}`;

  $("languageSelect").innerHTML = languageOptions();
  $("languageSelect").addEventListener("change", () => {
    setLanguage($("languageSelect").value);
    // The sidebar and every label are rendered with the language, so start over.
    window.location.reload();
  });

  $("passwordForm").addEventListener("submit", async (e) => {
    e.preventDefault();

    if ($("newPassword").value !== $("repeatPassword").value) {
      showToast(t("account.passwordsDontMatch"), "error");
      return;
    }

    const button = $("changePasswordButton");
    setButtonLoading(button, true, t("common.saving"));
    try {
      const response = await apiFetch("/auth/change-password", {
        method: "POST",
        body: JSON.stringify({
          current_password: $("currentPassword").value,
          new_password: $("newPassword").value
        })
      });
      const data = await readJson(response);
      if (!response.ok) {
        showToast(getErrorMessage(data, t("common.requestFailed")), "error");
        return;
      }
      showToast(t("account.passwordChanged"), "success");
      $("passwordForm").reset();
    } finally {
      setButtonLoading(button, false);
    }
  });
}
