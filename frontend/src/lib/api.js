import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

const http = axios.create({ baseURL: API, timeout: 30000 });

export const api = {
  liveTokens: (params = {}) => http.get("/tokens/live", { params }).then((r) => r.data),
  tokenDetail: (addr) => http.get(`/tokens/${addr}`).then((r) => r.data),
  ticker: () => http.get("/ticker").then((r) => r.data),
  kols: () => http.get("/kols").then((r) => r.data),
  addKol: (payload) => http.post("/kols", payload).then((r) => r.data),
  removeKol: (id) => http.delete(`/kols/${id}`).then((r) => r.data),
  kolCalls: () => http.get("/kols/calls").then((r) => r.data),
  narratives: () => http.get("/narratives").then((r) => r.data),
  positions: (params = {}) => http.get("/portfolio/positions", { params }).then((r) => r.data),
  buy: (payload) => http.post("/portfolio/buy", payload).then((r) => r.data),
  close: (payload) => http.post("/portfolio/close", payload).then((r) => r.data),
  partialClose: (payload) => http.post("/portfolio/partial-close", payload).then((r) => r.data),
  stats: () => http.get("/portfolio/stats").then((r) => r.data),
  tradeLog: (params = {}) => http.get("/portfolio/trade-log", { params }).then((r) => r.data),
  bankroll: () => http.get("/bankroll").then((r) => r.data),
  setBankroll: (payload) => http.put("/bankroll", payload).then((r) => r.data),
  resetBankroll: () => http.post("/bankroll/reset").then((r) => r.data),
  engine: () => http.get("/engine/status").then((r) => r.data),
  alerts: () => http.get("/alerts").then((r) => r.data),
  addAlert: (payload) => http.post("/alerts", payload).then((r) => r.data),
  removeAlert: (id) => http.delete(`/alerts/${id}`).then((r) => r.data),
  settings: () => http.get("/settings").then((r) => r.data),
  saveSettings: (payload) => http.put("/settings", payload).then((r) => r.data),
};
