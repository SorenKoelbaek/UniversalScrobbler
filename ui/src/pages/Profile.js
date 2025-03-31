import React, { useContext, useState } from "react";
import AuthContext from "../auth/AuthContext";
import {
  Card,
  CardContent,
  Typography,
  Button,
  Grid,
  Stack,
  CircularProgress,
} from "@mui/material";
import apiClient from "../utils/apiClient";
import { useSnackbar } from "../contexts/SnackbarContext";

const Profile = () => {
  const { user } = useContext(AuthContext);
  const [loading, setLoading] = useState(false);
  const apiUrl = process.env.REACT_APP_API_URL;

  const formatDateTime = (dateStr) => {
    const d = new Date(dateStr);
    const pad = (n) => String(n).padStart(2, "0");
    const day = pad(d.getDate());
    const month = pad(d.getMonth() + 1); // Months are 0-indexed
    const year = d.getFullYear();
    const hours = pad(d.getHours());
    const minutes = pad(d.getMinutes());
    const seconds = pad(d.getSeconds());

    return `${day}/${month}/${year} ${hours}:${minutes}:${seconds}`;
  };
  const { showSnackbar } = useSnackbar();

  const handleManualGather = async () => {
    setLoading(true);
    try {
      await apiClient.post("/spotify/gather-playback");
      showSnackbar("Playback history gathered!", "success");
    } catch (err) {
      console.error("Failed to gather playback history:", err);
      showSnackbar("Something went wrong.", "error");
    } finally {
      setLoading(false);
    }
  };
  const handleSpotifyReauthorize = () => {
  window.location.href = `${apiUrl}/spotify/login`;
};
  const handleDiscogsReauthorize = async () => {
    try {
      const res = await apiClient.get("/discogs/login"); // returns { url: "https://..." }
      if (res.data.url) {
        window.location.href = res.data.url;
      } else {
        console.error("No redirect URL received from backend");
      }
    } catch (err) {
      console.error("Error during Discogs login redirect:", err);
    }
  };
  const handleRefreshDiscogs = async () => {
    setLoading(true);
    setSuccess(false);
    try {
      await apiClient.post("/discogs/refresh");
      setSuccess(true);
    } catch (error) {
      console.error("Failed to trigger Discogs refresh:", error);
    } finally {
      setLoading(false);
    }
  };
  const [success, setSuccess] = useState(false);

  return (
    <Card sx={{ maxWidth: 500, margin: "2rem auto" }}>
      <CardContent>
        <Typography variant="h5" gutterBottom>
          Profile
        </Typography>

        {user ? (
          <Stack spacing={1} sx={{ mb: 2 }}>
            <Typography><strong>Username:</strong> {user.username}</Typography>
            <Typography><strong>Email:</strong> {user.email}</Typography>
            <Typography><strong>Status:</strong> {user.status || "N/A"}</Typography>
            <Typography><strong>User ID:</strong> {user.user_uuid}</Typography>
            {user.spotify_token && (
              <Typography variant="body2" color="text.secondary">
                Spotify token expires at: {formatDateTime(user.spotify_token.expires_at)}
              </Typography>
            )}
            {user.discogs_token && (
              <Typography variant="body2" color="text.secondary">
                Discogs access token: {user.discogs_token.access_token}
              </Typography>
            )}
          </Stack>
        ) : (
          <Typography>No user data available.</Typography>
        )}

        <Grid container spacing={2}>
          <Grid item>
            {!user.discogs_token && (<Button
              variant="outlined"
              color="secondary"
              onClick={handleSpotifyReauthorize}
              disabled={loading}
            >
              {loading ? <CircularProgress size={20} /> : "Authorize Spotify"}
            </Button>)}
            {!user.discogs_token && (<Button
              variant="outlined"
              color="secondary"
              onClick={handleDiscogsReauthorize}
              disabled={loading}
            >
              {loading ? <CircularProgress size={20} /> : "Authorize Discogs"}
            </Button>)}
            <Button
                variant="contained"
                color="primary"
                onClick={handleRefreshDiscogs}
                disabled={loading}
                sx={{ mt: 2 }}
              >
                {loading ? <CircularProgress size={24} /> : "Refresh Discogs Collection"}
              </Button>
              {success && (
                <Typography variant="body2" color="success.main" sx={{ mt: 1 }}>
                  Refresh triggered!
                </Typography>
              )}
          </Grid>
        </Grid>
      </CardContent>
    </Card>
  );
};

export default Profile;
