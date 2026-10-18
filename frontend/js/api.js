// Shared helper for talking to the Flask API.
const API_BASE = "http://127.0.0.1:5000/api";

const Auth = {
  getToken() {
    return localStorage.getItem("token");
  },
  getUser() {
    const raw = localStorage.getItem("user");
    return raw ? JSON.parse(raw) : null;
  },
  save(token, user) {
    localStorage.setItem("token", token);
    localStorage.setItem("user", JSON.stringify(user));
  },
  clear() {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
  },
  isLoggedIn() {
    return !!this.getToken();
  },
};

async function apiRequest(path, { method = "GET", body, auth = false } = {}) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (auth && Auth.getToken()) headers["Authorization"] = `Bearer ${Auth.getToken()}`;

  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch (networkError) {
    throw new Error("Cannot reach the server. Is the backend running?");
  }

  let data = {};
  try {
    data = await response.json();
  } catch (e) {
    // response had no JSON body
  }

  if (!response.ok) {
    // An expired or invalid token: log the user out so they can sign in again
    if (response.status === 401 && auth) Auth.clear();
    throw new Error(data.error || data.msg || `Request failed (${response.status})`);
  }
  return data;
}

const api = {
  // Auth
  register: (email, password, role, name) =>
    apiRequest("/auth/register", { method: "POST", body: { email, password, role, name } }),
  login: (email, password) =>
    apiRequest("/auth/login", { method: "POST", body: { email, password } }),
  me: () => apiRequest("/auth/me", { auth: true }),

  // Jobs
  listJobs: (params = {}) => {
    const query = new URLSearchParams(params).toString();
    return apiRequest(`/jobs${query ? "?" + query : ""}`);
  },
  getJob: (id) => apiRequest(`/jobs/${id}`, { auth: true }),
  createJob: (job) => apiRequest("/jobs", { method: "POST", body: job, auth: true }),
  myJobs: () => apiRequest("/jobs/mine", { auth: true }),

  // Applications
  apply: (jobId, coverLetter) =>
    apiRequest(`/jobs/${jobId}/apply`, { method: "POST", body: { cover_letter: coverLetter }, auth: true }),
  myApplications: () => apiRequest("/applications/mine", { auth: true }),
  jobApplicants: (jobId) => apiRequest(`/jobs/${jobId}/applications`, { auth: true }),
  setApplicationStatus: (id, status) =>
    apiRequest(`/applications/${id}`, { method: "PATCH", body: { status }, auth: true }),

  // Candidate profile
  getProfile: () => apiRequest("/profile/candidate", { auth: true }),
  updateProfile: (fields) => apiRequest("/profile/candidate", { method: "PUT", body: fields, auth: true }),
};