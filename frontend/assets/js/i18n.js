import { messages } from "./i18n-messages.js?v=9";

// Interface language. Stored per browser; defaults to the browser's language.

const LANG_KEY = "lang";

export const LANGUAGES = {
  en: { label: "English", locale: "en-US" },
  tr: { label: "Türkçe", locale: "tr-TR" },
  de: { label: "Deutsch", locale: "de-DE" }
};

export function getLanguage() {
  try {
    const saved = localStorage.getItem(LANG_KEY);
    if (saved && LANGUAGES[saved]) return saved;
  } catch {
    // Storage blocked: fall back to the browser language.
  }
  const browser = (navigator.language || "en").slice(0, 2).toLowerCase();
  return LANGUAGES[browser] ? browser : "en";
}

export function setLanguage(language) {
  try {
    localStorage.setItem(LANG_KEY, language);
  } catch {
    // Without storage the choice only lasts for this page.
  }
}

export function getLocale() {
  return LANGUAGES[getLanguage()].locale;
}

// Excel in Turkish and German expects ";" between columns and "," as decimal mark.
export function csvDelimiter() {
  return getLanguage() === "en" ? "comma" : "semicolon";
}

/** t("pager.range", { from: 1, to: 50, total: 230 }) */
export function t(key, vars = {}) {
  const language = getLanguage();
  const text = messages[language]?.[key] ?? messages.en[key] ?? key;
  return text.replace(/\{(\w+)\}/g, (match, name) => (name in vars ? vars[name] : match));
}

/**
 * Fills elements marked with data-i18n (text), data-i18n-placeholder,
 * data-i18n-title and data-i18n-aria-label.
 */
export function applyTranslations(root = document) {
  root.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });
  root.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
    el.placeholder = t(el.dataset.i18nPlaceholder);
  });
  root.querySelectorAll("[data-i18n-title]").forEach((el) => {
    el.title = t(el.dataset.i18nTitle);
  });
  root.querySelectorAll("[data-i18n-aria-label]").forEach((el) => {
    el.setAttribute("aria-label", t(el.dataset.i18nAriaLabel));
  });

  if (root === document) {
    document.documentElement.lang = getLanguage();
    const titleKey = document.body.dataset.titleKey;
    if (titleKey) document.title = `${t(titleKey)} · Eysto`;
  }
}

// The API answers in English; known messages are shown in the user's language.
const API_ERRORS = [
  [/^Not enough stock for product (.+) in (.+)$/, "err.notEnoughStockIn", ["product", "warehouse"]],
  [/^Not enough stock for product (.+)$/, "err.notEnoughStock", ["product"]],
  [/^(.+) is counted in '(.+)', so the quantity must be a whole number$/, "err.wholeNumber", ["product", "unit"]],
  [/^Product (\d+) not found$/, "err.productNotFound", []],
  [/^Product (\d+) is not part of this count$/, "err.productNotInCount", []],
  [/^Missing columns: (.+)$/, "err.missingColumns", ["columns"]]
];

const API_ERROR_KEYS = {
  "Invalid username or password": "err.invalidLogin",
  "User is inactive": "err.userInactive",
  "Too many failed login attempts. Try again later.": "err.tooManyAttempts",
  "Not enough permissions": "err.forbidden",
  "Barcode already exists": "err.barcodeExists",
  "Barcode belongs to an archived product. Restore it instead of creating a new one.": "err.barcodeArchived",
  "Product not found": "err.productNotFoundGeneric",
  "Category not found": "err.categoryNotFound",
  "Category already exists": "err.categoryExists",
  "Warehouse not found": "err.warehouseNotFound",
  "Warehouse already exists": "err.warehouseExists",
  "The default warehouse can't be deactivated": "err.defaultWarehouse",
  "Warehouse still has stock. Transfer it to another warehouse first.": "err.warehouseHasStock",
  "Supplier not found": "err.supplierNotFound",
  "Supplier already exists": "err.supplierExists",
  "Stock out is already cancelled": "err.alreadyCancelled",
  "This warehouse already has an open stock count": "err.countOpen",
  "There are no products to count": "err.countEmpty",
  "Enter at least one counted quantity first": "err.countNothing",
  "This stock count is already closed": "err.countClosed",
  "Username already exists": "err.usernameExists",
  "Email already exists": "err.emailExists",
  "You can't remove your own admin access": "err.ownAdmin",
  "At least one active admin is required": "err.lastAdmin",
  "Current password is incorrect": "err.wrongPassword",
  "New password must be different": "err.samePassword",
  "The file has no data rows": "err.emptyFile",
  "The file could not be read as CSV": "err.badCsv",
  "Product violates a data constraint": "err.constraint",
  "Internal server error": "err.server"
};

export function translateApiError(detail) {
  const key = API_ERROR_KEYS[detail];
  if (key) return t(key);

  for (const [pattern, messageKey, names] of API_ERRORS) {
    const match = detail.match(pattern);
    if (match) {
      const vars = Object.fromEntries(names.map((name, i) => [name, match[i + 1]]));
      return t(messageKey, vars);
    }
  }
  return detail;
}
