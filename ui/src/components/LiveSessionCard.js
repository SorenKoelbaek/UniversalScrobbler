import React, { useEffect, useRef, useState } from "react";
import {
  Card, CardContent, Typography, Chip, Box, Collapse, IconButton, Tooltip, Slider
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
  const [position, setPosition] = useState(0); // ms

  const audioRef = useRef(null);
  const navigate = useNavigate();

  // --- SSE subscription
  useEffect(() => {
    let ctrl = new AbortController();
    const sseUrl = `${process.env.REACT_APP_API_URL}/events`;

    fetchEventSource(sseUrl, {
      method: "GET",
      headers: { Authorization: `Bearer ${token}` },
      signal: ctrl.signal,
      openWhenHidden: true,
      onopen: (res) => {
        if (res.ok) {
          setConnected(true);
          console.log("✅ SSE connected");
        } else {
          console.error("❌ Failed to connect SSE", res);
        }
      },
      onmessage: (event) => {
        if (!event.data || event.data.trim() === "" || event.data.trim() === ":") return;
        try {
          const msg = JSON.parse(event.data);
          console.log("📡 SSE:", msg);

          if (msg.type === "timeline" && msg.now_playing) {
            setCurrentTrack({
              title: msg.now_playing.title,
              artist: msg.now_playing.artist,
              album: msg.now_playing.album,
              track_uuid: msg.now_playing.track_uuid,
              album_uuid: msg.now_playing.album_uuid ?? null,
              file_url: msg.now_playing.file_url,
              duration_ms: msg.now_playing.duration_ms,
            });
            setIsPlaying(msg.play_state === "playing");

            const audio = audioRef.current;
            if (msg.now_playing.file_url) {
              if (audio.src !== process.env.REACT_APP_API_URL + msg.now_playing.file_url) {
                audio.src = process.env.REACT_APP_API_URL + msg.now_playing.file_url;
                audio.load();
              }
              // sync position only if drift > 1s
              if (msg.now_playing.position_ms != null) {
                const target = msg.now_playing.position_ms / 1000;
                if (Math.abs(audio.currentTime - target) > 1) {
                  audio.currentTime = target;
                }
                setPosition(msg.now_playing.position_ms);
              }
              if (msg.play_state === "playing") {
                audio.play().catch(err => console.warn("⚠️ Play failed", err));
              } else {
                audio.pause();
              }
            }
          }
        } catch (err) {
          console.error("Error parsing SSE event", err, event.data);
        }
      },
      onclose: () => setConnected(false),
      onerror: (err) => {
        console.error("SSE Error:", err);
        setConnected(false);
      },
    });

    return () => ctrl.abort();
  }, [token]);

  // --- Update position as audio plays
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const handler = () => setPosition(audio.currentTime * 1000);
    audio.addEventListener("timeupdate", handler);
    return () => audio.removeEventListener("timeupdate", handler);
  }, [currentTrack]);

  // --- API calls
  const togglePlayPause = async () => {
    try {
      if (isPlaying) {
        await apiClient.post("/playback-sessions/pause", {}, { headers: { Authorization: `Bearer ${token}` } });
      } else {
        await apiClient.post("/playback-sessions/resume", {}, { headers: { Authorization: `Bearer ${token}` } });
      }
    } catch (err) {
      console.error("❌ Failed to toggle playback", err);
    }
  };

  const skipNext = async () => {
    try {
      await apiClient.post("/playback-sessions/next", {}, { headers: { Authorization: `Bearer ${token}` } });
    } catch (err) {
      console.error("❌ Failed to skip next", err);
    }
  };

  const skipPrevious = async () => {
    try {
      await apiClient.post("/playback-sessions/previous", {}, { headers: { Authorization: `Bearer ${token}` } });
    } catch (err) {
      console.error("❌ Failed to skip previous", err);
    }
  };

  const handleSeek = async (_, value) => {
    try {
      await apiClient.post("/playback-sessions/seek", { position_ms: value }, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const audio = audioRef.current;
      if (audio) audio.currentTime = value / 1000;
      setPosition(value);
    } catch (err) {
      console.error("❌ Failed to seek", err);
    }
  };

  return (
    <Card sx={{ width: 360 }}>
      {/* Hidden audio element */}
      <audio ref={audioRef} preload="auto" />

      {/* Header */}
      <CardContent sx={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <Typography variant="subtitle1" sx={{ flexGrow: 1 }}>
          {collapsed && currentTrack ? `${currentTrack.title} by ${currentTrack.artist}` : ""}
          <Chip
            icon={connected ? <StreamIcon sx={{ color: "white" }} /> : <HeartBrokenIcon sx={{ color: "white" }} />}
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
              <Box sx={{ position: "relative", textAlign: "center" }}>
                <Typography variant="subtitle1" fontWeight="bold" color="white">
                  {currentTrack.title}
                </Typography>
                <Typography variant="body2" sx={{ opacity: 0.8 }} color="white">
                  {currentTrack.artist}
                </Typography>
                <Typography variant="caption" sx={{ opacity: 0.6 }} color="white">
                  {currentTrack.album}
                </Typography>
                {currentTrack.album_uuid && (
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

                {/* Seek Slider */}
                <Slider
                  value={position}
                  min={0}
                  max={currentTrack.duration_ms ?? 1}
                  step={1000}
                  onChange={(_, value) => setPosition(value)}
                  onChangeCommitted={handleSeek}
                  sx={{ mt: 2 }}
                />
              </Box>
            ) : (
              <Typography variant="body2" color="textSecondary">No track playing.</Typography>
            )}
          </CardContent>

          {/* Playback Ribbon */}
          <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", bgcolor: "grey.900", color: "white", px: 1, py: 0.5 }}>
            <IconButton color="inherit" size="small" onClick={skipPrevious}><SkipPreviousIcon /></IconButton>
            <IconButton color="inherit" size="small" onClick={togglePlayPause}>
              {isPlaying ? <PauseIcon /> : <PlayArrowIcon />}
            </IconButton>
            <IconButton color="inherit" size="small" onClick={skipNext}><SkipNextIcon /></IconButton>
            <IconButton color="inherit" size="small"><MenuIcon /></IconButton>
            <IconButton color="inherit" size="small" onClick={() => setCollapsed(true)}><ExpandLessIcon /></IconButton>
          </Box>
        </Card>
      </Collapse>
    </Card>
  );
};

export default LiveSessionCard;
