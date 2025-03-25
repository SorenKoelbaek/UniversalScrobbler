import React, { useEffect, useState } from "react";
import {
  Card,
  CardContent,
  Typography,
  Chip,
  Stack,
  LinearProgress,
} from "@mui/material";
import apiClient from "../utils/apiClient"; // Import your apiClient
import { fetchEventSource } from '@microsoft/fetch-event-source';

const LiveSessionCard = ({ token }) => {
  const [connected, setConnected] = useState(false);
  const [currentTrack, setCurrentTrack] = useState(null);
  const [progressMs, setProgressMs] = useState(0);

  useEffect(() => {
    // Function to get SSE stream with the token
    const fetchSSEStream = async () => {
      const sseUrl = `${process.env.REACT_APP_API_URL}/events`;

      try {
        await fetchEventSource(sseUrl, {
          method: "GET", // Define the HTTP method
          headers: {
            "Authorization": `Bearer ${token}`, // Attach the Bearer token in the request headers
          },
          onopen: (response) => {
            if (response.ok) {
              setConnected(true);
            } else {
              console.error("Failed to connect to SSE");
            }
          },
          onmessage: (event) => {
            try {
              const msg = JSON.parse(event.data);

              if (msg.type === "current_play" && msg.data) {
                const { track_name, artist_name, album_name, duration_ms, progress_ms, is_still_playing } = msg.data;

                setCurrentTrack({
                  track_name,
                  artist_name,
                  album_name,
                  duration_ms,
                  is_still_playing,
                });

                setProgressMs(progress_ms || 0);
              }
            } catch (err) {
              console.log("📨 Non-JSON message:", event.data);
            }
          },
          onclose: () => {
            console.log("❌ SSE disconnected");
            setConnected(false);
          },
          onerror: (err) => {
            console.error("SSE Error: ", err);
          },
        });
      } catch (error) {
        console.error("Error with SSE connection: ", error);
      }
    };

    fetchSSEStream();

  }, [token]);

  const progressPercent =
    currentTrack?.duration_ms > 0
      ? Math.min((progressMs / currentTrack.duration_ms) * 100, 100)
      : 0;

  return (
    <Card sx={{ maxWidth: 400 }}>
      <CardContent>
        <Stack direction="row" alignItems="center" justifyContent="space-between" mb={1}>
          <Typography variant="h6">Live Session</Typography>
          <Chip
            label={connected ? "Connected" : "Disconnected"}
            color={connected ? "success" : "error"}
            size="small"
          />
        </Stack>

        {currentTrack ? (
          <>
            <Typography><strong>Track:</strong> {currentTrack.track_name}</Typography>
            <Typography><strong>Artist:</strong> {currentTrack.artist_name}</Typography>
            <Typography><strong>Album:</strong> {currentTrack.album_name}</Typography>

            <Stack mt={2}>
              <LinearProgress
                variant="determinate"
                value={progressPercent}
              />
              <Typography variant="caption" color="textSecondary">
                {Math.floor(progressMs / 1000)}s /{" "}
                {Math.floor(currentTrack.duration_ms / 1000)}s
              </Typography>
            </Stack>
          </>
        ) : (
          <Typography variant="body2" color="textSecondary">
            No track playing.
          </Typography>
        )}
      </CardContent>
    </Card>
  );
};

export default LiveSessionCard;
