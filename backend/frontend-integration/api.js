// Backend API client (React / koi bhi JS frontend). src/api/client.js mein copy karo.
// .env (Vite): VITE_API_URL=http://localhost:5000   |  CRA: REACT_APP_API_URL=http://localhost:5000
const BASE = (import.meta?.env?.VITE_API_URL || process.env.REACT_APP_API_URL || "http://localhost:5000") + "/api";

let token = (typeof localStorage !== "undefined" && localStorage.getItem("token")) || null;
export const setToken = (t) => {
  token = t;
  if (typeof localStorage !== "undefined") t ? localStorage.setItem("token", t) : localStorage.removeItem("token");
};
export const isLoggedIn = () => !!token;

async function request(path, { method = "GET", json, form, raw } = {}) {
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  let body;
  if (json !== undefined) { headers["Content-Type"] = "application/json"; body = JSON.stringify(json); }
  if (form) body = form; // FormData: Content-Type browser khud lagata hai
  const res = await fetch(BASE + path, { method, headers, body });
  if (res.status === 401 && token) { setToken(null); }
  if (!res.ok) {
    let err = {}; try { err = await res.json(); } catch {}
    const e = new Error(err.error || `HTTP ${res.status}`);
    e.status = res.status; e.details = err.details; // upload mein rejected files yahin milti hain
    throw e;
  }
  if (raw) return res;
  return res.status === 204 ? null : res.json();
}

// ---- Auth ----
export async function login(username, password) {
  const r = await request("/auth/login", { method: "POST", json: { username, password } });
  setToken(r.access_token);
  return r.user;
}
export const register = (username, email, password) =>
  request("/auth/register", { method: "POST", json: { username, email, password } });
export const me = () => request("/auth/me");
export const logout = () => setToken(null);

// ---- Inspections ----
// files: File[] (input type=file multiple). meta: {title, location, notes, inspection_id}
export function uploadImages(files, meta = {}) {
  const form = new FormData();
  files.forEach((f) => form.append("images", f));
  Object.entries(meta).forEach(([k, v]) => v != null && v !== "" && form.append(k, v));
  return request("/inspections/upload", { method: "POST", form }); // -> {inspection, images, rejected}
}
export const analyze = (id, { force = false } = {}) =>
  request(`/inspections/${id}/analyze${force ? "?force=true" : ""}`, { method: "POST" });
export const getInspection = (id) => request(`/inspections/${id}`);
export const listInspections = (params = {}) =>
  request("/inspections?" + new URLSearchParams(params)); // status,q,from,to,page,per_page,order
export const getImages = (id) => request(`/inspections/${id}/images`);
export const getDetections = (id, params = {}) =>
  request(`/inspections/${id}/detections?` + new URLSearchParams(params));
export const getDetection = (id) => request(`/detections/${id}`);
export const verifyDetection = (id, status, comment) =>
  request(`/detections/${id}/verify`, { method: "POST", json: { status, comment } });
export const deleteInspection = (id) => request(`/inspections/${id}`, { method: "DELETE" });

// analyze background mein chalta hai -> status poll karo jab tak khatam na ho
export async function waitForAnalysis(id, { intervalMs = 1500, timeoutMs = 600000, onProgress } = {}) {
  const t0 = Date.now();
  for (;;) {
    const insp = await getInspection(id);
    onProgress?.(insp); // insp.images_processed / insp.image_count se progress bar
    if (["completed", "partial", "failed"].includes(insp.status)) return insp;
    if (Date.now() - t0 > timeoutMs) throw new Error("Analysis timed out");
    await new Promise((r) => setTimeout(r, intervalMs));
  }
}

// ---- Dashboard ----
export const dashboardSummary = () => request("/dashboard/summary");
export const defectStats = (params = {}) => request("/dashboard/defect-stats?" + new URLSearchParams(params));
export const modelInfo = () => request("/model/info");

// ---- Images: <img src> mein seedha use karo (token query param se auth hota hai) ----
// path = image.original_url / image.annotated_url ; width = thumbnail ke liye
export const imageUrl = (path, width) =>
  path ? `${BASE.replace(/\/api$/, "")}${path}?token=${token}${width ? `&w=${width}` : ""}` : null;

// ---- Reports (file download) ----
async function download(path, filename) {
  const res = await request(path, { raw: true });
  const url = URL.createObjectURL(await res.blob());
  const a = Object.assign(document.createElement("a"), { href: url, download: filename });
  a.click();
  URL.revokeObjectURL(url);
}
export const downloadPdf = (id) => download(`/reports/${id}/pdf`, `inspection_${id}_report.pdf`);
export const downloadCsv = (params = {}) =>
  download("/reports/export/csv?" + new URLSearchParams(params), "detections_export.csv");
