import React, { useContext } from "react";
import { Navigate } from "react-router-dom";
import AuthContext from "./AuthContext";

const ProtectedRoute = ({ children }) => {
  const { auth } = useContext(AuthContext);

  if (!auth?.user) {
    return <Navigate to="/" />;
  }

  return children;
};

export default ProtectedRoute;
