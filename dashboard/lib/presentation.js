export const unavailable = (value, formatter = String) =>
  value === null || value === undefined || value === "" ? "—" : formatter(value);

export const numeric = (value, suffix = "", digits = 0) =>
  typeof value === "number" && Number.isFinite(value)
    ? `${value.toFixed(digits)}${suffix}`
    : "—";

export function eventCategory(event = {}) {
  const source = `${event.type || ""} ${event.description || ""}`.toUpperCase();
  if (source.includes("BREAK") || source.includes("INCIDENT") || source.includes("FAIL")) return "INCIDENT";
  if (source.includes("TRAFFIC") || source.includes("CONGEST")) return "TRAFFIC";
  if (source.includes("MESH") || source.includes("CLOUD") || source.includes("SOS")) return "MESH";
  if (source.includes("PPO") || source.includes("DECISION") || source.includes("REPOSITION")) return "DECISION";
  if (source.includes("ASSIGN") || source.includes("TRANSFER") || source.includes("BID") || source.includes("RECOVER")) return "DISPATCH";
  if (source.includes("DELIVER") || source.includes("COMPLETE")) return "DELIVERY";
  return "SYSTEM";
}

export const eventTime = (event = {}) =>
  event.time_str || (event.timestamp !== undefined ? `${event.timestamp}m` : "—");
