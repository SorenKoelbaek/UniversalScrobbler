import React, { useEffect, useState, useRef } from "react";
import {
  Card,
  CardContent,
  Typography,
  Chip,
  Stack,
  LinearProgress,
} from "@mui/material";

const LiveSessionCard = ({ token }) => {
  const [connected, setConnected] = useState(false);
  const [currentTrack, setCurrentTrack] = useState(null);
  const [progressMs, setProgressMs] = useState(0);
  const intervalRef = useRef(null);

  const wsUrl = `${process.env.REACT_APP_WS_URL}?token=${token}`;

  useEffect(() => {
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log("✅ WebSocket connected");
      setConnected(true);
      ws.send("Hello from dashboard");
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        console.log(msg);
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

          // Reset timer if needed
          if (intervalRef.current) clearInterval(intervalRef.current);

          if (is_still_playing) {
            intervalRef.current = setInterval(() => {
              setProgressMs((prev) => {
                if (duration_ms && prev < duration_ms) {
                  return prev + 1000;
                } else {
                  clearInterval(intervalRef.current);
                  return prev;
                }
              });
            }, 1000);
          }
        }
      } catch (err) {
        console.log("📨 Non-JSON message:", event.data);
      }
    };

    ws.onclose = () => {
      console.log("❌ WebSocket disconnected");
      setConnected(false);
      if (intervalRef.current) clearInterval(intervalRef.current);
    };

    return () => {
      ws.close();
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [wsUrl]);

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
