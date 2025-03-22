import React, { useContext, useEffect } from "react";
import { BrowserRouter as Router, Routes, Route, Link, Navigate, useNavigate, useLocation } from "react-router-dom";
import { AppBar, Toolbar, Typography, Button, Box } from "@mui/material";
import Login from "./pages/Login";
import AuthContext from "./auth/AuthContext";
import UserMenu from "./components/UserMenu";
import Profile from "./pages/Profile"; // near the top with other imports
import Dashboard from "./pages/Dashboard";
import SpotifyCallback from "./pages/SpotifyCallback";


const App = () => {
  const { auth, logout, user, loading } = useContext(AuthContext);
  const navigate = useNavigate(); // Initialize the useNavigate hook
  const location = useLocation(); // Get the current route

  // Redirect to preferred garden after login and data fetch
    useEffect(() => {
      if (
          !loading &&
          auth?.user &&
          location.pathname === "/" // Only redirect if on the main page
          ) {
        console.log("Hello",auth?.user)
      }
    }, [auth, user, loading, navigate]);

  return (
      <>
      <AppBar position="static" sx={{ backgroundColor: "#4caf50" }}>
        <Toolbar>
         <Typography
          variant="h6"
          sx={{ flexGrow: 1, cursor: "pointer", textDecoration: "none", color: "inherit" }}
          component={Link}
          to="/"
        >
          Universal Scrobbler
        </Typography>
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
          <Route path="/" element={<Dashboard />} />
          <Route path="/login" element={<Login />} />
          <Route path="/profile" element={<Profile />} />
          <Route path="/spotify/callback" element={<SpotifyCallback />} />
        </Routes>
      </Box>
    </>
  );
};

export default App;
