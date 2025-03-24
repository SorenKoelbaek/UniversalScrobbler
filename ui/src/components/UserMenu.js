import React, { useContext, useState } from "react";
import { Link } from "react-router-dom";
import AuthContext from "../auth/AuthContext";
import "./UserMenu.css";

const UserMenu = () => {
  const { logout } = useContext(AuthContext);
  const [open, setOpen] = useState(false);

  return (
    <div className="user-menu">
      <button onClick={() => setOpen(!open)}>☰</button>
      {open && (
        <div className="menu-dropdown">
          <Link to="/dashboard" onClick={() => setOpen(false)}>Dashboard</Link>
          <Link to="/profile" onClick={() => setOpen(false)}>Profile</Link>
          <button onClick={logout}>Bye!</button>
        </div>
      )}
    </div>
  );
};

export default UserMenu;
