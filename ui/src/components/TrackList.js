import React from "react";
import {
  Box,
  Typography,
  List,
  ListItem,
  ListItemText,
  Button,
} from "@mui/material";
import { Link } from "react-router-dom";

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

  return (
    <Box>
      <Typography variant="h6" gutterBottom>
        Tracklist
      </Typography>
      <List disablePadding>
        {sorted.map(([trackNum, group]) => (
          <React.Fragment key={trackNum}>
            <Typography variant="subtitle2" sx={{ mt: 2 }}>
              {trackNum !== "Unnumbered" ? `Track ${trackNum}` : "Unnumbered Tracks"}
            </Typography>
            {group.map((track, idx) => (
              <ListItem
                key={track.track_uuid}
                disablePadding
                sx={{ pl: 2, py: 0.5 }}
              >
                <ListItemText
                  primary={
                    <Button
                      component={Link}
                      to={`/track/${track.track_uuid}`}
                      sx={{
                        padding: 0,
                        minWidth: 0,
                        textTransform: "none",
                      }}
                    >
                      {track.track_number
                        ? `${track.track_number}. ${track.name}`
                        : `${idx + 1}. ${track.name}`}
                    </Button>
                  }
                />
              </ListItem>
            ))}
          </React.Fragment>
        ))}
      </List>
    </Box>
  );
};

export default TrackList;
