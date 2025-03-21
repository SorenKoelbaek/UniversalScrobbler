import React, { createContext, useState, useEffect } from "react";
import axios from "axios";
import {jwtDecode} from "jwt-decode";

const AuthContext = createContext();
const apiUrl = process.env.REACT_APP_API_URL;

export const AuthProvider = ({ children }) => {
  const [auth, setAuth] = useState(() => {
    const token = localStorage.getItem("access_token");
    if (token) {
      try {
        const decoded = jwtDecode(token);
        if (decoded.exp * 1000 > Date.now()) {
          return { token, user: decoded.sub };
        }
      } catch {
        // Invalid token
        localStorage.removeItem("access_token");
      }
    }
    return null;
  });

  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState(null);

  const fetchUser = async () => {
    try {
      if (auth?.token) {
        const response = await axios.get(`${apiUrl}/me`, {
          headers: { Authorization: `Bearer ${auth.token}` },
        });
        setUser(response.data);
      }
    } catch (err) {
      console.error("Failed to fetch user data:", err);
      logout();
    } finally {
      setLoading(false); // Ensure loading is set to false regardless of success/failure
    }
  };

  const login = async (username, password) => {
    try {
      const params = new URLSearchParams();
      params.append("username", username);
      params.append("password", password);

      const response = await axios.post(`${apiUrl}/token`, params, {
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
      });

      const { access_token } = response.data;
      const decoded = jwtDecode(access_token);

      // Update auth state and save token
      setAuth({ token: access_token, user: decoded.sub });
      localStorage.setItem("access_token", access_token);

      // Fetch user details
      await fetchUser();
    } catch (err) {
      console.error("Login error:", err.response?.data?.detail || err.message);
      throw err;
    }
  };

  const logout = () => {
    setAuth(null);
    setUser(null);
    localStorage.removeItem("access_token");
  };

  const isTokenExpired = () => {
    if (auth?.token) {
      const decoded = jwtDecode(auth.token);
      return decoded.exp * 1000 <= Date.now();
    }
    return true;
  };

  useEffect(() => {
    if (auth && !isTokenExpired()) {
      fetchUser();
    } else if (auth) {
      logout(); // Logout if the token is expired
    } else {
      setLoading(false); // No token, stop loading
    }
  }, [auth]);

  return (
    <AuthContext.Provider value={{ auth, user, loading, login, logout, setUser }}>
      {!loading && children} {/* Render children only after loading is complete */}
    </AuthContext.Provider>
  );
};

export default AuthContext;
