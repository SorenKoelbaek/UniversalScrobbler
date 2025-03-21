import React, { useContext, useEffect } from "react";
import { BrowserRouter as Router, Routes, Route, Link, Navigate, useNavigate, useLocation } from "react-router-dom";
import { AppBar, Toolbar, Typography, Button, Box } from "@mui/material";
import Login from "./pages/Login";
import AuthContext from "./auth/AuthContext";

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
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            Universal Scrobbler
          </Typography>
          {auth?.user ? (
            <>
              <Button color="inherit" onClick={logout}>
                Logout
              </Button>
            </>
          ) : (
            <Button color="inherit" component={Link} to="/login">
              Login
            </Button>
          )}
        </Toolbar>
      </AppBar>
      <Box sx={{ padding: 2 }}>
        <Routes>
          <Route path="/login" element={<Login />} />
        </Routes>
      </Box>
    </>
  );
};

export default App;
