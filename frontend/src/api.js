import axios from "axios";

export const api = axios.create({ 
  baseURL: import.meta.env.VITE_API_BASE || "http://localhost:8000",
  timeout: 300000 // 5 minutes timeout for long-running story generation requests
});

// Token management
const TOKEN_KEY = "auth_token";

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (token) => {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
    api.defaults.headers.common["Authorization"] = `Bearer ${token}`;
  } else {
    localStorage.removeItem(TOKEN_KEY);
    delete api.defaults.headers.common["Authorization"];
  }
};

// Initialize token if it exists
const existingToken = getToken();
if (existingToken) {
  api.defaults.headers.common["Authorization"] = `Bearer ${existingToken}`;
}

// Auth API functions
export const googleLogin = () => {
  // Redirect to backend Google OAuth endpoint
  const backendUrl = import.meta.env.VITE_API_BASE || "http://localhost:8000";
  window.location.href = `${backendUrl}/api/auth/google/login`;
};

export const getCurrentUser = () => api.get("/api/auth/me").then(r => r.data);

export const logout = async () => {
  try {
    await api.post("/api/auth/logout");
  } catch (e) {
    console.error("Logout error:", e);
  } finally {
    setToken(null);
  }
};

// API functions
export const listChapters = () => api.get("/api/chapters").then(r=>r.data);
export const getQuestions = (chapter) => api.get(`/api/questions`, { params: { chapter } }).then(r=>r.data);
export const upsertQuestions = (chapter_id, questions) => api.post(`/api/questions`, { chapter_id, questions }).then(r=>r.data);
export const addAnswer = (payload) => api.post(`/api/answers`, payload);
export const getAnswers = (person_id, chapter) => api.get(`/api/answers`, { params: { person_id, chapter } }).then(r=>r.data);
export const storyChapter = (payload) => api.post(`/api/story/chapter`, payload).then(r=>r.data);
export const getStoryChapter = (chapter_id) => api.get(`/api/story/chapter/${chapter_id}`).then(r => {
  // Backend now returns null instead of 404, so we can return it directly
  return r.data;
}).catch(err => {
  // Fallback: still handle 404 in case backend changes
  if (err.response?.status === 404) {
    return null;
  }
  throw err;
});
export const storyCompile = (payload) => api.post(`/api/story/compile`, payload).then(r=>r.data);
