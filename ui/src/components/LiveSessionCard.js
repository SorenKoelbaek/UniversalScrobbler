// LiveSessionCard.js
import React, { useEffect, useState } from "react";
import {
  Card,
  CardContent,
  Typography,
  Chip,
  Stack,
  Box,
} from "@mui/material";
import { fetchEventSource } from "@microsoft/fetch-event-source";
import StreamIcon from "@mui/icons-material/Stream";
import HeartBrokenIcon from "@mui/icons-material/HeartBroken";
import "./LiveSessionCard.css";

const LiveSessionCard = ({ token }) => {
  const [connected, setConnected] = useState(false);
  const [currentTrack, setCurrentTrack] = useState(null);
  const [progressMs, setProgressMs] = useState(0);

  useEffect(() => {
    const fetchSSEStream = async () => {
      const sseUrl = `${process.env.REACT_APP_API_URL}/events`;

      try {
        await fetchEventSource(sseUrl, {
          method: "GET",
          headers: {
            Authorization: `Bearer ${token}`,
          },
          onopen: (response) => {
            if (response.ok) {
              setConnected(true);
            } else {
              console.error("Failed to connect to SSE");
            }
          },
          onmessage: (event) => {
            if (!event.data || event.data.trim() === "") return;

            try {
              const msg = JSON.parse(event.data);
              console.log(msg);
              if (msg.type === "current_play" && msg.data) {
                const {
                  spotify_track_id,
                  track_name,
                  artist_name,
                  album_name,
                  discogs_release_id,
                  played_at,
                  source,
                  device_name,
                  progress_ms,
                  duration_ms,
                  full_play,
                  is_still_playing,
                } = msg.data;

                setCurrentTrack({
                  spotify_track_id,
                  track_name,
                  artist_name,
                  album_name,
                  discogs_release_id,
                  played_at,
                  source,
                  device_name,
                  progress_ms,
                  duration_ms,
                  full_play,
                  is_still_playing,
                });

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

  const isPlaying = currentTrack?.is_still_playing;

  return (
    <Card sx={{ maxWidth: 400 }}>
      <CardContent>
        <Stack
          direction="row"
          alignItems="center"
          justifyContent="space-between"
          mb={2}
        >
          <Typography variant="h6">Now spinning:</Typography>
          <Chip
            icon={
              connected ? (
                <StreamIcon sx={{ color: "white" }} />
              ) : (
                <HeartBrokenIcon sx={{ color: "white" }} />
              )
            }
            label=""
            color={connected ? "success" : "error"}
            size="small"
            sx={{ px: 1 }}
          />
        </Stack>

        {currentTrack ? (
          <Box
            sx={{
              position: "relative",
              display: "flex",
              justifyContent: "center",
              alignItems: "center",
              height: 300,
            }}
          >
            {/* Animated Aura Ring */}
            <div className={`ring ${!isPlaying ? "paused" : ""}`}>
              <i style={{ "--clr": "#00ff0a" }}></i>
              <i style={{ "--clr": "#ff0057" }}></i>
              <i style={{ "--clr": "#fffd44" }}></i>

              {/* Vinyl Center */}
              <div className="vinyl">
                <Typography variant="subtitle1" fontWeight="bold" color="white">
                  {currentTrack.track_name}
                </Typography>
                <Typography variant="body2" sx={{ opacity: 0.8 }} color="white">
                  {currentTrack.artist_name}
                </Typography>
                <Typography variant="caption" sx={{ opacity: 0.6 }} color="white">
                  {currentTrack.album_name}
                </Typography>
              </div>
            </div>
          </Box>
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
