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
import InfoIcon from "@mui/icons-material/Info";
import KeyboardArrowDownIcon from "@mui/icons-material/KeyboardArrowDown";
import KeyboardArrowUpIcon from "@mui/icons-material/KeyboardArrowUp";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import PauseIcon from "@mui/icons-material/Pause";
import SkipNextIcon from "@mui/icons-material/SkipNext";
import SkipPreviousIcon from "@mui/icons-material/SkipPrevious";
import MenuIcon from "@mui/icons-material/Menu";
import ExpandLessIcon from "@mui/icons-material/ExpandLess";
import "./LiveSessionCard.css";
import apiClient from "../utils/apiClient";
import { useNavigate } from "react-router-dom";

const LiveSessionCard = ({ token }) => {
  const [collapsed, setCollapsed] = useState(false);
  const [connected, setConnected] = useState(false);
  const [currentTrack, setCurrentTrack] = useState(null);
  const [isPlaying, setIsPlaying] = useState(false);

  const navigate = useNavigate();

  useEffect(() => {
    const fetchPlaybackSession = async () => {
      try {
        const res = await apiClient.get("/playback-sessions/me", {
          headers: { Authorization: `Bearer ${token}` },
        });

        setCurrentTrack(
          res.data.current_track ?? {
            song_title: "—",
            artists: [{ name: "—" }],
            album_title: "—",
            album_uuid: null,
            full_update: false,
          }
        );
        setIsPlaying(res.data.play_state === "playing");
      } catch (err) {
        console.error("❌ Failed to load playback session", err);
      }
    };

    let ctrl = new AbortController();
    const sseUrl = `${process.env.REACT_APP_API_URL}/events`;

    fetchEventSource(sseUrl, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
      },
      signal: ctrl.signal,
      openWhenHidden: true, // keep alive in background
      onopen: (response) => {
        if (response.ok) {
          setConnected(true);
          console.log("✅ SSE connected");
        } else {
          console.error("❌ Failed to connect to SSE", response);
        }
      },
      onmessage: (event) => {
          if (!event.data || event.data.trim() === "" || event.data.trim() === ":") {
            return; // skip keepalive ping
          }
          try {
            const msg = JSON.parse(event.data);

            if (msg.message) {
              fetchPlaybackSession();
            }
          } catch (err) {
            console.error("Error parsing SSE event", err, event.data);
          }
        },

      onclose: () => {
        console.log("❌ SSE disconnected, will retry…");
        setConnected(false);
      },
      onerror: (err) => {
        console.error("SSE Error:", err);
        setConnected(false);
        // allow fetch-event-source to retry automatically
      },
    });

    // Initial snapshot load
    fetchPlaybackSession();

    return () => {
      ctrl.abort(); // cleanup on unmount
    };
  }, [token]);

  const togglePlayPause = () => {
    setIsPlaying((prev) => !prev);
    // TODO: hook up to backend playback control
  };

  return (
    <Card sx={{ width: 360 }}>
      {/* Header */}
      <CardContent sx={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <Typography variant="subtitle1" sx={{ flexGrow: 1 }}>
          {collapsed && currentTrack
            ? `${currentTrack.song_title} by ${currentTrack.artists[0]?.name}`
            : ""}
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

      {/* Expanded content */}
      <Collapse in={!collapsed}>
        <Card sx={{ maxWidth: 400 }}>
          <CardContent>
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
                <div className={`ring ${!isPlaying ? "paused" : ""}`}>
                  <i style={{ "--clr": "#115c13", opacity: 0.8 }}></i>
                  <i style={{ "--clr": "#780834", opacity: 0.8 }}></i>
                  <i style={{ "--clr": "#15a6d3", opacity: 0.8 }}></i>

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
                    {currentTrack.full_update && (
                      <Tooltip title="Go to album">
                        <IconButton
                          size="small"
                          onClick={() => navigate(`/album/${currentTrack.album_uuid}`)}
                          sx={{ ml: 1, p: 0.5 }}
                        >
                          <InfoIcon sx={{ color: "white", opacity: 0.6 }} />
                        </IconButton>
                      </Tooltip>
                    )}
                  </div>
                </div>
              </Box>
            ) : (
              <Typography variant="body2" color="textSecondary">
                No track playing.
              </Typography>
            )}
          </CardContent>

          {/* Playback Ribbon */}
          <Box
            sx={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              bgcolor: "grey.900",
              color: "white",
              px: 1,
              py: 0.5,
            }}
          >
            <IconButton color="inherit" size="small">
              <SkipPreviousIcon />
            </IconButton>

            <IconButton color="inherit" size="small" onClick={togglePlayPause}>
              {isPlaying ? <PauseIcon /> : <PlayArrowIcon />}
            </IconButton>

            <IconButton color="inherit" size="small">
              <SkipNextIcon />
            </IconButton>

            <IconButton color="inherit" size="small">
              <MenuIcon />
            </IconButton>

            <IconButton color="inherit" size="small" onClick={() => setCollapsed(true)}>
              <ExpandLessIcon />
            </IconButton>
          </Box>
        </Card>
      </Collapse>
    </Card>
  );
};

export default LiveSessionCard;
