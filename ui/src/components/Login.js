import React, { useState, useContext } from "react";
import AuthContext from "../auth/AuthContext";
import {useSnackbar} from "../contexts/SnackbarContext";
import { useSnackbar } from "../contexts/SnackbarContext";


const Login = () => {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const { login } = useContext(AuthContext);
  const { showSnackbar } = useSnackbar();

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      await login(username, password);
      showSnackbar("Login successful!","success");
    } catch (err) {
      showSnackbar("Login failed!","error");
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <input
        type="text"
        placeholder="Username"
        value={username}
        onChange={(e) => setUsername(e.target.value)}
      />
      <input
        type="password"
        placeholder="Password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />
      <button type="submit">Login</button>
    </form>
  );
};

export default Login;
