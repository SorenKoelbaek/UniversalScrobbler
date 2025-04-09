// LiveSessionCard.js
import React, { useEffect, useState } from "react";
import {
  Card,
  CardContent,
  Typography,
  Chip,
  Stack,
  Box,
  Collapse,
  IconButton,
  Tooltip,
} from "@mui/material";
import { fetchEventSource } from "@microsoft/fetch-event-source";
import StreamIcon from "@mui/icons-material/Stream";
import HeartBrokenIcon from "@mui/icons-material/HeartBroken";
import InfoIcon from '@mui/icons-material/Info';
import "./LiveSessionCard.css";
import apiClient from "../utils/apiClient";
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import { useNavigate } from "react-router-dom";

const LiveSessionCard = ({ token }) => {
  const [collapsed, setCollapsed] = useState(false);
  const [connected, setConnected] = useState(false);
  const [currentTrack, setCurrentTrack] = useState(null);
  const [progressMs, setProgressMs] = useState(0);

  const navigate = useNavigate();

  useEffect(() => {
  const fetchCurrentTrack = async () => {
    try {
      const res = await apiClient.get("/consumption/currently-playing");
      // Match the shape expected from SSE messages
      setCurrentTrack({
        ...res.data,
        is_still_playing: true, // Assumed true if it’s “currently playing”
      });
    } catch (err) {
      if (err.response?.status !== 404) {
        console.error("Failed to load currently playing track", err);
      }
    }
  };

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
          if (!event.data || event.data.trim() === "" || event.data.trim() === ":") return;

          try {
            const clean = event.data.startsWith("data: ")
              ? event.data.slice(6).trim()
              : event.data.trim();

            const msg = JSON.parse(clean);

            if (msg.message) {
              console.log(msg);
              setCurrentTrack(msg.message);
            }
          } catch (err) {
            console.error("Error parsing SSE event", err);
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

  // First fetch the current track, then subscribe to SSE
  fetchCurrentTrack().finally(fetchSSEStream);
}, [token]);



  const isPlaying = currentTrack?.is_still_playing;
  return (
      <Card sx={{ width: 360 }}>
      <CardContent sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="subtitle1" sx={{ flexGrow: 1 }}>
          {collapsed ? currentTrack.song_title + " by "+currentTrack.artists[0].name :""}
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
        </Typography>
        <IconButton onClick={() => setCollapsed(!collapsed)}>
          {collapsed ? <KeyboardArrowUpIcon /> : <KeyboardArrowDownIcon />}
        </IconButton>
      </CardContent>

      <Collapse in={!collapsed}>
    <Card sx={{ maxWidth: 400 }}>
      <CardContent>
        <Stack
          direction="row"
          alignItems="center"
          justifyContent="space-between"
          mb={2}
        >
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
              <i style={{ "--clr": "#115c13", opacity: 0.8  }}></i>
              <i style={{ "--clr": "#780834", opacity: 0.8  }}></i>
              <i style={{ "--clr": "#15a6d3", opacity: 0.8  }}></i>

              {/* Vinyl Center */}
              <div className="vinyl">
                <Typography variant="subtitle1" fontWeight="bold" color="white">
                  {currentTrack.song_title}
                </Typography>
                <Typography variant="body2" sx={{ opacity: 0.8 }} color="white">
                  {currentTrack.artists[0]?.name}
                </Typography>
                <Typography variant="caption" sx={{ opacity: 0.6 }} color="white">
                  {currentTrack.album_title}
                </Typography>
                <Typography variant="body2" sx={{ opacity: 0.6, display: "flex", alignItems: "center" }} color="white">
                  {currentTrack.full_update && (
                    <Tooltip title="Go to album">
                      <IconButton
                        size="small"
                        onClick={() => navigate(`/album/${currentTrack.album_uuid}`)}
                        sx={{ ml: 1, p: 0.5 }} // minimal spacing
                      >
                        <InfoIcon sx={{ color: "white", opacity: 0.6 }} />
                      </IconButton>
                    </Tooltip>
                  )}
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
        </Collapse>
      </Card>
  );
};

export default LiveSessionCard;
