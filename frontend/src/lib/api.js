import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

const client = axios.create({ baseURL: API });

client.interceptors.request.use((config) => {
  const token = localStorage.getItem("surginote_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

client.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err?.response?.status === 401) {
      localStorage.removeItem("surginote_token");
      localStorage.removeItem("surginote_user");
      if (window.location.pathname !== "/login") window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);

export const api = {
  register: (body) => client.post("/auth/register", body).then((r) => r.data),
  login: (body) => client.post("/auth/login", body).then((r) => r.data),
  me: () => client.get("/auth/me").then((r) => r.data),

  listPatients: () => client.get("/patients").then((r) => r.data),
  listDischarged: () => client.get("/patients/discharged").then((r) => r.data),
  readmitPatient: (id) => client.post(`/patients/${id}/readmit`).then((r) => r.data),
  createPatient: (body) => client.post("/patients", body).then((r) => r.data),
  getPatient: (id) => client.get(`/patients/${id}`).then((r) => r.data),
  updatePatient: (id, body) => client.patch(`/patients/${id}`, body).then((r) => r.data),
  dischargePatient: (id) => client.delete(`/patients/${id}`).then((r) => r.data),

  importCenso: (file, confirm) => {
    const form = new FormData();
    form.append("file", file, file.name);
    return client.post(`/patients/import-censo?confirm=${confirm ? "true" : "false"}`, form, {
      headers: { "Content-Type": "multipart/form-data" },
      timeout: 60000,
    }).then((r) => r.data);
  },
  importCensoStatus: (jobId) => client.get(`/patients/import-censo/status/${jobId}`).then((r) => r.data),

  pasteAdmissionNote: (id, text) => client.post(`/patients/${id}/admission-note`, { text }).then((r) => r.data),
  listAdditionalNotes: (id) => client.get(`/patients/${id}/additional-notes`).then((r) => r.data),
  addAdditionalNote: (id, source, text) => client.post(`/patients/${id}/additional-notes`, { source, text }).then((r) => r.data),
  deleteAdditionalNote: (id, noteId) => client.delete(`/patients/${id}/additional-notes/${noteId}`).then((r) => r.data),

  listEntries: (id) => client.get(`/patients/${id}/entries`).then((r) => r.data),
  getTodayEntry: (id) => client.get(`/patients/${id}/entries/today`).then((r) => r.data),
  updateTodayEntry: (id, body) => client.patch(`/patients/${id}/entries/today`, body).then((r) => r.data),

  generatePase: (id, date) => client.post(`/patients/${id}/generate/pase`, { date }).then((r) => r.data),
  generateNote: (id, date) => client.post(`/patients/${id}/generate/note`, { date }).then((r) => r.data),
  generateNoChanges: (id, date) => client.post(`/patients/${id}/generate/no-changes`, { date }).then((r) => r.data),
  generateAdmission: (id, date) => client.post(`/patients/${id}/generate/admission`, { date }).then((r) => r.data),
  fullPase: () => client.post("/pase/today").then((r) => r.data),

  transcribe: (blob) => {
    const form = new FormData();
    form.append("audio", blob, "voice.webm");
    return client.post("/transcribe", form, {
      headers: { "Content-Type": "multipart/form-data" },
      timeout: 120000,
    }).then((r) => r.data);
  },
};

export default client;
