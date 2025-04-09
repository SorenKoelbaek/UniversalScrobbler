import React, { useContext, useEffect } from "react";
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Link,
  Navigate,
  useNavigate,
  useLocation
} from "react-router-dom";
import { AppBar, Toolbar, Typography, Button, Box } from "@mui/material";

import Login from "./pages/Login";
import AuthContext from "./auth/AuthContext";
import UserMenu from "./components/UserMenu";
import Profile from "./pages/Profile";
import Dashboard from "./pages/Dashboard";
import Landing from "./pages/Landing";
import Collection from "./pages/Collection";
import SpotifyCallback from "./pages/SpotifyCallback";
import DiscogsCallback from "./pages/DiscogsCallback";
import ProtectedRoute from "./auth/ProtectedRoute";
import AlbumDetail from "./pages/AlbumDetail";

import LiveSessionCard from "./components/LiveSessionCard"; // ✅ added

const navLinks = [
  { label: "Collection", path: "/collection" },
  { label: "Listening History", path: "/listening-history" },
  { label: "Discover", path: "/discover" },
];

const App = () => {
  const { auth, logout, user, loading } = useContext(AuthContext);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    if (!loading && auth?.user && location.pathname === "/") {
      // Future redirect?
    }
  }, [auth, user, loading, navigate]);

  // ✅ determine when to show the floating card
  const shouldShowLiveCard =
    auth?.user &&
    !["/", "/login", "/spotify/callback", "/discogs/callback"].includes(location.pathname);

  return (
    <>
      <AppBar position="static" sx={{ backgroundColor: "#4caf50" }}>
        <Toolbar>
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            <Link
              to="/"
              style={{ textDecoration: "none", color: "inherit", cursor: "pointer" }}
            >
              Universal Scrobbler
            </Link>
          </Typography>
          {auth?.user && (
            <Box sx={{ display: "flex" }}>
              {navLinks.map((link) => (
                <Button key={link.label} color="inherit" component={Link} to={link.path}>
                  {link.label}
                </Button>
              ))}
            </Box>
          )}
          {auth?.user ? (
            <UserMenu />
          ) : (
            <Button color="inherit" component={Link} to="/login">
              Show ticket
            </Button>
          )}
        </Toolbar>
      </AppBar>

      <Box sx={{ padding: 2 }}>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route
            path="/spotify/callback"
            element={<ProtectedRoute><SpotifyCallback /></ProtectedRoute>}
          />
          <Route
            path="/discogs/callback"
            element={<ProtectedRoute><DiscogsCallback /></ProtectedRoute>}
          />
          <Route
            path="/collection"
            element={<ProtectedRoute><Collection /></ProtectedRoute>}
          />
          <Route
            path="/album/:album_uuid"
            element={<ProtectedRoute><AlbumDetail /></ProtectedRoute>}
          />
          <Route
            path="/dashboard"
            element={<ProtectedRoute><Dashboard /></ProtectedRoute>}
          />
          <Route
            path="/profile"
            element={<ProtectedRoute><Profile /></ProtectedRoute>}
          />
        </Routes>
      </Box>

      {/* ✅ Hovering card rendered conditionally at the end */}
      {shouldShowLiveCard && (
        <div style={{
          position: 'fixed',
          bottom: 16,
          right: 16,
          zIndex: 1300,
          maxWidth: 360,
        }}>
          <LiveSessionCard token={auth?.token} />
        </div>
      )}
    </>
  );
};

export default App;
