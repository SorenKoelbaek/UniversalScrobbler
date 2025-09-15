// components/LiveSessionCard.jsx
import React, { useEffect, useRef, useState } from "react";
import {
  Card, CardContent, Typography, Chip, Box, Collapse,
  IconButton, Tooltip, Slider
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
import PlaybackQueueList from "./PlaybackQueueList";
import SpeakerIcon from "@mui/icons-material/Speaker";


const LiveSessionCard = ({ token }) => {
  const [collapsed, setCollapsed] = useState(false);
  const [connected, setConnected] = useState(false);
  const [currentTrack, setCurrentTrack] = useState(null);
  const [queue, setQueue] = useState([]);
  const [isPlaying, setIsPlaying] = useState(false);
  const [position, setPosition] = useState(0);
  const [showQueue, setShowQueue] = useState(false);
  const [thisDevice, setThisDevice] = useState(null);

  const audioRef = useRef(null);
  const navigate = useNavigate();
  const [devices, setDevices] = useState([]);
  const [showDevices, setShowDevices] = useState(false);
  const [activeDevice, setActiveDevice] = useState(null);
  // --- Queue helpers
  const handleReorder = async (newOrder) => {
    try {
      await apiClient.post("/playback-sessions/reorder", { queue: newOrder }, {
        headers: { Authorization: `Bearer ${token}` },
      });
    } catch (err) {
      console.error("❌ Failed to reorder queue", err);
    }
  };

const handleJump = async (item) => {
  try {
    await apiClient.post("/playback-sessions/jump", {
      playback_queue_uuid: item.playback_queue_uuid,
    }, {
      headers: { Authorization: `Bearer ${token}` },
    });
  } catch (err) {
    console.error("❌ Failed to jump to track", err);
  }
};

  // --- API: fetch current playback state
  const fetchQueue = async () => {
    try {
      const res = await apiClient.get("/playback-sessions", {
        headers: { Authorization: `Bearer ${token}` },
      });
      setQueue(res.data.tracks || []);
      if (res.data.now_playing) {
        setCurrentTrack({
          title: res.data.now_playing.track.name,
          artist: res.data.now_playing.track.artists.map((a) => a.name).join(", "),
          album: res.data.now_playing.track.albums?.[0]?.title ?? "—",
          track_uuid: res.data.now_playing.track.track_uuid,
          track_version_uuid: res.data.now_playing.track_version_uuid,
          album_uuid: res.data.now_playing.track.albums?.[0]?.album_uuid ?? null,
          file_url: res.data.now_playing.file_url,
          duration_ms: res.data.now_playing.duration_ms,
        });
      }
    } catch (err) {
      console.error("❌ Failed to fetch queue", err);
    }
  };

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
          fetchQueue();
        } else {
          console.error("❌ Failed to connect SSE", res);
        }
      },
      onmessage: (event) => {
          if (!event.data || event.data.trim() === "" || event.data.trim() === ":") return;
          try {
            const msg = JSON.parse(event.data);
            console.log("📡 SSE message:", msg);
            if (msg.devices) {
              setDevices(msg.devices);
            }
            if (msg.active_device_uuid) {
              setActiveDevice(msg.active_device_uuid);
            }
            if (msg.this_device_uuid) {
              setThisDevice(msg.this_device_uuid);
            }
            const isActiveDevice = msg.active_device_uuid === msg.this_device_uuid;

            if (msg.type === "timeline") {
              setIsPlaying(msg.play_state === "playing");

              if (msg.now_playing) {
                setCurrentTrack({
                  title: msg.now_playing.title,
                  artist: msg.now_playing.artist,
                  album: msg.now_playing.album,
                  track_uuid: msg.now_playing.track_uuid,
                  track_version_uuid: msg.now_playing.track_version_uuid,
                  album_uuid: msg.now_playing.album_uuid ?? null,
                  file_url: msg.now_playing.file_url,
                  duration_ms: msg.now_playing.duration_ms,
                });

                // 🔹 Only load/play audio if this is the active device
                if (isActiveDevice) {
                  const audio = audioRef.current;
                  const newSrc = process.env.REACT_APP_API_URL + msg.now_playing.file_url;

                  if (audio.src !== newSrc) {
                    audio.src = newSrc;
                    audio.load();
                  }

                  if (msg.play_state === "playing") {
                    if (msg.now_playing.position_ms !== undefined) {
                      const targetTime = msg.now_playing.position_ms / 1000;
                      if (Math.abs(audio.currentTime - targetTime) > 0.25) {
                        audio.currentTime = targetTime;
                      }
                    }
                    audio.play().catch((err) => console.warn("⚠️ Play failed", err));
                  } else {
                    audio.pause();
                  }
                } else {
                  // 🔹 Not active → always pause audio
                  if (audioRef.current) audioRef.current.pause();
                }
              }

              fetchQueue();
            } else if (msg.type === "heartbeat") {
              if (msg.position_ms !== undefined) {
                setPosition(msg.position_ms);
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

  useEffect(() => {
    if (!thisDevice) return;
    const interval = setInterval(() => {
      apiClient.post(
        "/ping",
        { device_uuid: thisDevice },
        { headers: { Authorization: `Bearer ${token}` } }
      ).catch((err) => {
        console.warn("⚠️ Ping failed", err);
      });
    }, 15000); // every 15 seconds

    return () => clearInterval(interval);
  }, [thisDevice, token]);

  // --- Update local position
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    const handler = () => setPosition(audio.currentTime * 1000);
    audio.addEventListener("timeupdate", handler);
    return () => audio.removeEventListener("timeupdate", handler);
  }, [currentTrack]);

  // --- Auto-skip when track ends
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const handleEnded = async () => {
      try {
        await apiClient.post("/playback-sessions/next", {}, {
          headers: { Authorization: `Bearer ${token}` },
        });
      } catch (err) {
        console.error("❌ Failed to auto-skip next", err);
      }
    };

    audio.addEventListener("ended", handleEnded);
    return () => audio.removeEventListener("ended", handleEnded);
  }, [token]);

  // --- API controls
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
  const skipNext = async () =>
    apiClient.post("/playback-sessions/next", {}, { headers: { Authorization: `Bearer ${token}` } });
  const skipPrevious = async () =>
    apiClient.post("/playback-sessions/previous", {}, { headers: { Authorization: `Bearer ${token}` } });
  const handleSeek = async (_, value) => {
    try {
      await apiClient.post("/playback-sessions/seek", { position_ms: value }, { headers: { Authorization: `Bearer ${token}` } });
      const audio = audioRef.current;
      if (audio) audio.currentTime = value / 1000;
      setPosition(value);
    } catch (err) {
      console.error("❌ Failed to seek", err);
    }
  };

  return (
    <Card sx={{ width: 360 }}>
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
              <Box sx={{ textAlign: "center" }}>
                <Typography variant="subtitle1" fontWeight="bold">{currentTrack.title}</Typography>
                <Typography variant="body2" sx={{ opacity: 0.8 }}>{currentTrack.artist}</Typography>
                <Typography variant="caption" sx={{ opacity: 0.6 }}>{currentTrack.album}</Typography>
                {currentTrack.album_uuid && (
                  <Tooltip title="Go to album">
                    <IconButton size="small" onClick={() => navigate(`/album/${currentTrack.album_uuid}`)} sx={{ ml: 1, p: 0.5 }}>
                      <InfoIcon sx={{ color: "white", opacity: 0.6 }} />
                    </IconButton>
                  </Tooltip>
                )}

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

          {/* Queue Drawer */}
          <Collapse in={showQueue} timeout="auto" unmountOnExit>
            <Box sx={{ maxHeight: 240, overflowY: "auto", bgcolor: "grey.100" }}>
              <PlaybackQueueList
                queue={queue}
                currentTrack={currentTrack}
                onPlayTrack={handleJump}
                onReorder={handleReorder}
              />
            </Box>
          </Collapse>

          {/* Playback Ribbon */}
          <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", bgcolor: "grey.900", color: "white", px: 1, py: 0.5 }}>
            <IconButton color="inherit" size="small" onClick={skipPrevious}><SkipPreviousIcon /></IconButton>
            <IconButton color="inherit" size="small" onClick={togglePlayPause}>
              {isPlaying ? <PauseIcon /> : <PlayArrowIcon />}
            </IconButton>
            <IconButton color="inherit" size="small" onClick={skipNext}><SkipNextIcon /></IconButton>
            <IconButton color="inherit" size="small" onClick={() => setShowQueue((prev) => !prev)}><MenuIcon /></IconButton>
            <IconButton color="inherit" size="small" onClick={() => setShowDevices((prev) => !prev)}>
                <SpeakerIcon />
              </IconButton>
            <IconButton color="inherit" size="small" onClick={() => setCollapsed(true)}><ExpandLessIcon /></IconButton>
          </Box>
          <Collapse in={showDevices} timeout="auto" unmountOnExit>
              <Box sx={{ maxHeight: 180, overflowY: "auto", bgcolor: "grey.800", color: "white", px: 1, py: 1 }}>
                {devices.length === 0 && (
                  <Typography variant="caption" sx={{ opacity: 0.6 }}>
                    No devices connected
                  </Typography>
                )}
                {devices.map((d) => {
                  const isActive = d.device_uuid === activeDevice;
                  const isThis = d.device_uuid === thisDevice;

                  return (
                    <Box
                      key={d.device_uuid}
                      sx={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        py: 0.5,
                        cursor: "pointer",
                        bgcolor: isActive ? "grey.700" : "transparent",
                        borderRadius: 1,
                        px: 1,
                        "&:hover": { bgcolor: "grey.600" },
                      }}
                      onClick={async () => {
                        try {
                          await apiClient.post("/playback-sessions/switch", {
                            device_uuid: d.device_uuid,
                          }, { headers: { Authorization: `Bearer ${token}` } });
                          setActiveDevice(d.device_uuid);
                        } catch (err) {
                          console.error("❌ Failed to switch device", err);
                        }
                      }}
                    >
                      <Typography variant="body2">
                        {d.device_name}
                      </Typography>
                      <Box sx={{ display: "flex", gap: 1 }}>
                        {isThis && <Chip label="This device" size="small" color="info" />}
                        {isActive && <Chip label="Active" size="small" color="success" />}
                      </Box>
                    </Box>
                  );
                })}

              </Box>
            </Collapse>

        </Card>
      </Collapse>
    </Card>
  );
};

export default LiveSessionCard;
