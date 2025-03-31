import React, { useEffect, useContext, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import AuthContext from "../auth/AuthContext";
import apiClient from "../utils/apiClient";
import { useSnackbar } from "../contexts/SnackbarContext";

const DiscogsCallback = () => {
  const [searchParams] = useSearchParams();
  const { user } = useContext(AuthContext);
  const navigate = useNavigate();
  const { showSnackbar } = useSnackbar();

  const hasExchanged = useRef(false);  // 🛡️ Block double exchange

  useEffect(() => {
    const oauth_token = searchParams.get("oauth_token");
    const oauth_verifier = searchParams.get("oauth_verifier");

    if (!oauth_token || !user || hasExchanged.current) {
      return;
    }

    hasExchanged.current = true;  // ✅ Set the flag

    const exchangeToken = async () => {
      try {
        await apiClient.post("/discogs/authorize", { oauth_token, oauth_verifier });
        showSnackbar("Discogs account linked!", "success");
        navigate("/profile");
      } catch (error) {
        showSnackbar("Failed to exchange Discogs token!", "error");
        console.error("Failed to exchange Discogs token:", error);
      }
    };

    exchangeToken();
  }, [searchParams, user, navigate, showSnackbar]);

  return <p>Linking your Discogs account...</p>;
};

export default DiscogsCallback;
