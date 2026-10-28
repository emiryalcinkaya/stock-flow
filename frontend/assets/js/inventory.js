import { apiFetch, readJson } from "./config.js?v=6";
import { t } from "./i18n.js?v=6";
import { escapeHtml, formatNumber } from "./ui.js?v=6";

// Shared lookups (units, categories, warehouses, suppliers) used by several pages.

async function getJson(endpoint) {
  const response = await apiFetch(endpoint);
  const data = await readJson(response);
  if (!response.ok) throw new Error(data?.detail || `Failed to load ${endpoint}`);
  return data;
}

export const loadUnits = () => getJson("/units");
export const loadCategories = () => getJson("/categories");
export const loadWarehouses = () => getJson("/warehouses");
export const loadSuppliers = () => getJson("/suppliers");
export const loadWarehouseStock = (warehouseId) => getJson(`/warehouses/${warehouseId}/stock`);

export function unitLabel(code) {
  return t(`unit.${code}`);
}

export function formatQuantity(value, unit) {
  const amount = formatNumber(value);
  return unit ? `${amount} ${unitLabel(unit)}` : amount;
}

export function isWholeUnit(units, unitCode) {
  const unit = units.find((u) => u.code === unitCode);
  return unit ? unit.whole : true;
}

// Input step for a quantity field: whole units count in 1s, others allow 3 decimals.
export function quantityStep(units, unitCode) {
  return isWholeUnit(units, unitCode) ? "1" : "0.001";
}

export function unitOptions(units, selected = "pcs") {
  return units
    .map(
      (unit) => `
        <option value="${escapeHtml(unit.code)}" ${unit.code === selected ? "selected" : ""}>
          ${escapeHtml(t(`unitName.${unit.code}`))} (${escapeHtml(unitLabel(unit.code))})
        </option>
      `
    )
    .join("");
}

export function categoryOptions(categories, selected = null, emptyLabel = t("common.noCategory")) {
  return [
    `<option value="">${escapeHtml(emptyLabel)}</option>`,
    ...categories.map(
      (category) => `
        <option value="${category.id}" ${category.id === selected ? "selected" : ""}>
          ${escapeHtml(category.name)}
        </option>
      `
    )
  ].join("");
}

export function warehouseOptions(warehouses, selected = null) {
  const selectedId = selected ?? warehouses.find((w) => w.is_default)?.id;
  return warehouses
    .map(
      (warehouse) => `
        <option value="${warehouse.id}" ${warehouse.id === selectedId ? "selected" : ""}>
          ${escapeHtml(warehouse.name)}${warehouse.is_default ? ` (${escapeHtml(t("common.default"))})` : ""}
        </option>
      `
    )
    .join("");
}

export function supplierOptions(suppliers, selected = null) {
  return [
    `<option value="">${escapeHtml(t("common.noSupplier"))}</option>`,
    ...suppliers.map(
      (supplier) => `
        <option value="${supplier.id}" ${supplier.id === selected ? "selected" : ""}>${escapeHtml(supplier.name)}</option>
      `
    )
  ].join("");
}

export const STOCK_OUT_REASONS = ["sale", "consumption", "waste", "return_to_supplier", "other"];

export function reasonLabel(reason) {
  return t(`reason.${reason}`);
}

export function reasonOptions(selected = "sale", { includeAll = false } = {}) {
  const options = STOCK_OUT_REASONS.map(
    (reason) => `<option value="${reason}" ${reason === selected ? "selected" : ""}>${escapeHtml(reasonLabel(reason))}</option>`
  );
  if (includeAll) options.unshift(`<option value="">${escapeHtml(t("common.allReasons"))}</option>`);
  return options.join("");
}

export function movementLabel(reason) {
  return t(`movement.${reason}`);
}

// Turns an empty input into null and anything else into a number.
export function optionalNumber(value) {
  return value === "" || value === null || value === undefined ? null : Number(value);
}
