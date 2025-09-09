import React from "react";
import {
  Box,
  Typography,
  List,
  ListItem,
  ListItemText,
  IconButton,
  Tooltip,
} from "@mui/material";
import { Link } from "react-router-dom";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import QueueMusicIcon from "@mui/icons-material/QueueMusic";
import apiClient from "../utils/apiClient";

const TrackList = ({ tracks }) => {
  if (!tracks || tracks.length === 0) return null;

  const grouped = tracks.reduce((groups, track) => {
    const num = track.track_number || "Unnumbered";
    if (!groups[num]) groups[num] = [];
    groups[num].push(track);
    return groups;
  }, {});

  const sorted = Object.entries(grouped).sort(([a], [b]) => {
    const aNum = parseInt(a, 10);
    const bNum = parseInt(b, 10);
    if (!isNaN(aNum) && !isNaN(bNum)) return aNum - bNum;
    if (!isNaN(aNum)) return -1;
    if (!isNaN(bNum)) return 1;
    return 0;
  });

  const handlePlay = async (track_uuid) => {
      try {
        await apiClient.post("/playback-sessions/play", { track_uuid });
        console.log("Play requested:", track_uuid);
      } catch (err) {
        console.error("Failed to start playback", err);
      }
    };

    const handleQueue = async (track_uuid) => {
      try {
        await apiClient.post("/playback-sessions/queue", { track_uuid });
        console.log("queue requested:", track_uuid);
      } catch (err) {
        console.error("Failed to add to queue", err);
      }
    };


  return (
    <Box>
      <Typography variant="h6" gutterBottom>
        Tracklist
      </Typography>
      <List disablePadding>
        {sorted.map(([trackNum, group]) => (
          <React.Fragment key={trackNum}>
            <Typography variant="subtitle2" sx={{ mt: 2 }}>
            </Typography>
            {group.map((track, idx) => (
              <ListItem
                key={track.track_uuid}
                disablePadding
                sx={{
                  pl: 2,
                  py: 0.5,
                  display: "flex",
                  justifyContent: "space-between",
                  "&:hover .track-actions": { opacity: 1 },
                }}
              >
                <ListItemText
                  primary={
                    <Typography
                      component={Link}
                      to={`/track/${track.track_uuid}`}
                      sx={{
                        textDecoration: "none",
                        color: "inherit",
                        "&:hover": { textDecoration: "underline" },
                      }}
                    >
                      {track.track_number
                        ? `${track.track_number}. ${track.name}`
                        : `${idx + 1}. ${track.name}`}
                    </Typography>
                  }
                />
                    <Box
                      className="track-actions"
                      sx={{ opacity: 0, transition: "opacity 0.2s" }}
                    >
                      <Tooltip title="Play">
                        <IconButton
                          size="small"
                          onClick={() => handlePlay(track.track_uuid)}
                        >
                          <PlayArrowIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Add to Queue">
                        <IconButton
                          size="small"
                          onClick={() => handleQueue(track.track_uuid)}
                        >
                          <QueueMusicIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </Box>
              </ListItem>
            ))}
          </React.Fragment>
        ))}
      </List>
    </Box>
  );
};

export default TrackList;
