import React, { useEffect, useContext } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import AuthContext from "../auth/AuthContext";
import apiClient from "../utils/apiClient";
import { useSnackbar } from "../contexts/SnackbarContext";

const SpotifyCallback = () => {
  const [searchParams] = useSearchParams();
  const { user } = useContext(AuthContext);
  const navigate = useNavigate();
  const { showSnackbar } = useSnackbar();

  useEffect(() => {
    const code = searchParams.get("code");

    if (!code || !user) {
      console.error("Missing code or user context");
      return;
    }

    const exchangeToken = async () => {
      try {
        await apiClient.post("/spotify/authorize", { code });
        showSnackbar("Spotify account linked!", "success");
        navigate("/profile");
      } catch (error) {
        showSnackbar("Failed to exchange Spotify token!", "error");
        console.error("Failed to exchange Spotify token:", error);
      }
    };

    exchangeToken();
  }, [searchParams, user, navigate]);

  return <p>Linking your Spotify account...</p>;
};

export default SpotifyCallback;
