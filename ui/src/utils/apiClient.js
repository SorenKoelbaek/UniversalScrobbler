import axios from "axios";
const apiUrl = process.env.REACT_APP_API_URL;

const apiClient = axios.create({
  baseURL: apiUrl,
});

apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem("access_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

export default apiClient;