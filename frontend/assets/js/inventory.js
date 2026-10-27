import { apiFetch, readJson } from "./config.js";
import { escapeHtml } from "./ui.js";

// Shared lookups (units, categories, warehouses) used by several pages.

async function getJson(endpoint) {
  const response = await apiFetch(endpoint);
  const data = await readJson(response);
  if (!response.ok) throw new Error(data?.detail || `Failed to load ${endpoint}`);
  return data;
}

export const loadUnits = () => getJson("/units");
export const loadCategories = () => getJson("/categories");
export const loadWarehouses = () => getJson("/warehouses");
export const loadWarehouseStock = (warehouseId) => getJson(`/warehouses/${warehouseId}/stock`);

const quantityFormatter = new Intl.NumberFormat("en-US", { maximumFractionDigits: 3 });

export function formatQuantity(value, unit) {
  const amount = quantityFormatter.format(Number(value || 0));
  return unit ? `${amount} ${unit}` : amount;
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
          ${escapeHtml(unit.label)} (${escapeHtml(unit.code)})
        </option>
      `
    )
    .join("");
}

export function categoryOptions(categories, selected = null, emptyLabel = "No category") {
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
          ${escapeHtml(warehouse.name)}${warehouse.is_default ? " (default)" : ""}
        </option>
      `
    )
    .join("");
}

export const STOCK_OUT_REASONS = {
  sale: "Sale",
  consumption: "Internal use",
  waste: "Waste / damage",
  return_to_supplier: "Return to supplier",
  other: "Other"
};

export const MOVEMENT_LABELS = {
  initial: "Opening stock",
  restock: "Stock in",
  stock_out: "Stock out",
  adjustment: "Adjustment",
  sale: "Sale",
  sale_cancelled: "Cancelled stock out",
  transfer_in: "Transfer in",
  transfer_out: "Transfer out",
  ...STOCK_OUT_REASONS
};

// Turns an empty input into null and anything else into a number.
export function optionalNumber(value) {
  return value === "" || value === null || value === undefined ? null : Number(value);
}
