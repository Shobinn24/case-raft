import axios from "axios";

// In dev, Vite proxy handles /auth and /api -> Flask
// In production, set VITE_API_URL to the backend URL
const API_BASE = import.meta.env.VITE_API_URL || "";

const api = axios.create({
  baseURL: API_BASE,
  withCredentials: true,
});

// Auth
export const getAuthStatus = () => api.get("/auth/status");
export const logout = () => api.post("/auth/logout");
export const getLoginUrl = () => `${API_BASE}/auth/login`;

// Cases
export const getCases = (status) =>
  api.get("/api/cases", { params: { status } });
export const getCase = (caseId) => api.get(`/api/cases/${caseId}`);

// Reports
export const generateReport = (caseId, reportType = "case_summary") =>
  api.post("/api/reports/generate", { case_id: caseId, report_type: reportType });
export const getReportHistory = () => api.get("/api/reports/history");
export const getReportDownloadUrl = (reportId) =>
  `${API_BASE}/api/reports/${reportId}/download`;
