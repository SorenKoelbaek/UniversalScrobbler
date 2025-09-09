import React, { createContext, useState, useEffect } from "react";
import { jwtDecode } from "jwt-decode";
import apiClient from "../utils/apiClient";

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [auth, setAuth] = useState(() => {
    const token = localStorage.getItem("access_token");
    const expiry = parseInt(localStorage.getItem("access_token_expiry"), 10);

    if (token && expiry && expiry > Date.now()) {
      try {
        const decoded = jwtDecode(token);
        return { token, user: decoded.sub };
      } catch {
        localStorage.removeItem("access_token");
        localStorage.removeItem("access_token_expiry");
      }
    }
    return null;
  });

  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState(null);

  const fetchUser = async () => {
    try {
      if (auth?.token) {
        const response = await apiClient.get("/me");
        setUser(response.data);
      }
    } catch (err) {
      console.error("Failed to fetch user data:", err);
      logout();
    } finally {
      setLoading(false);
    }
  };

  const login = async (username, password) => {
    try {
      const params = new URLSearchParams();
      params.append("username", username);
      params.append("password", password);

      const response = await apiClient.post("/token", params, {
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
      });

      const { access_token, refresh_token, expires_at } = response.data;
      const decoded = jwtDecode(access_token);

      setAuth({ token: access_token, user: decoded.sub });
      localStorage.setItem("access_token", access_token);
      localStorage.setItem("refresh_token", refresh_token);
      localStorage.setItem("access_token_expiry", new Date(expires_at).getTime());

      await fetchUser();
    } catch (err) {
      console.error("Login error:", err.response?.data?.detail || err.message);
      throw err;
    }
  };

  const refreshAccessToken = async () => {
    const refreshToken = localStorage.getItem("refresh_token");
    if (!refreshToken) {
      logout();
      return;
    }

    try {
      const params = new URLSearchParams();
      params.append("grant_type", "refresh_token");
      params.append("refresh_token", refreshToken);

      const response = await apiClient.post("/refresh-token", params, {
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
      });

      const { access_token, refresh_token: newRefresh, expires_at } = response.data;
      const decoded = jwtDecode(access_token);

      setAuth({ token: access_token, user: decoded.sub });
      localStorage.setItem("access_token", access_token);
      localStorage.setItem("refresh_token", newRefresh);
      localStorage.setItem("access_token_expiry", new Date(expires_at).getTime());

      console.info("🔄 Access token refreshed");
    } catch (err) {
      console.error("Failed to refresh access token:", err);
      logout();
    }
  };

  const logout = async () => {
  try {
    const refreshToken = localStorage.getItem("refresh_token");
    if (refreshToken) {
      const params = new URLSearchParams();
      params.append("grant_type", "refresh_token");
      params.append("refresh_token", refreshToken);

      await apiClient.post("/revoke-token", params, {
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
      });
      console.info("🔒 Refresh token revoked");
    }
  } catch (err) {
    console.warn("Failed to revoke refresh token", err);
  } finally {
    setAuth(null);
    setUser(null);
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem("access_token_expiry");
  }
};

  const isTokenExpired = () => {
    if (auth?.token) {
      try {
        const decoded = jwtDecode(auth.token);
        return decoded.exp * 1000 <= Date.now();
      } catch {
        return true;
      }
    }
    return true;
  };

  // Initial check
  useEffect(() => {
    if (auth && !isTokenExpired()) {
      fetchUser();
    } else if (auth) {
      refreshAccessToken(); // try to refresh instead of logging out immediately
    } else {
      setLoading(false);
    }
  }, [auth]);

  return (
    <AuthContext.Provider value={{ auth, user, loading, login, logout, setUser }}>
      {!loading && children}
    </AuthContext.Provider>
  );
};

export default AuthContext;
