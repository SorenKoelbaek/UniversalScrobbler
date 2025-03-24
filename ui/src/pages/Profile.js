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
          </Stack>
        ) : (
          <Typography>No user data available.</Typography>
        )}

        <Grid container spacing={2}>
          <Grid item>
            <Button
              variant="outlined"
              color="secondary"
              onClick={handleManualGather}
              disabled={loading}
            >
              {loading ? <CircularProgress size={20} /> : "Manually gather playbacks"}
            </Button>
          </Grid>
        </Grid>
      </CardContent>
    </Card>
  );
};

export default Profile;
