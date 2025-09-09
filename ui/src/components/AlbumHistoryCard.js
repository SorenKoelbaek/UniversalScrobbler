import React from "react";
import {
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Avatar,
  Typography,
  Box,
  IconButton,
  Table,
  TableBody,
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import QueueMusicIcon from "@mui/icons-material/QueueMusic";
import apiClient from "../utils/apiClient";

const AlbumHistoryCard = ({ listens }) => {
  const { album_uuid, title, artists, release_date } = listens[0];
  const artistNames = artists?.map((a) => a.name).join(", ") || "—";
  const formattedDate = release_date
    ? new Date(release_date).toLocaleDateString()
    : "—";
  const mostRecentPlay = listens[0]?.played_at
    ? new Date(listens[0].played_at).toLocaleString()
    : "—";

  const handlePlay = async (e) => {
    e.stopPropagation();
    try {
      await apiClient.post("/playback-sessions/play", { album_uuid });
    } catch (err) {
      console.error("Failed to start playback", err);
    }
  };

  const handleAddToQueue = async (e) => {
    e.stopPropagation();
    try {
      await apiClient.post("/playback-sessions/queue", { album_uuid });
    } catch (err) {
      console.error("Failed to add to queue", err);
    }
  };

  return (
    <Accordion disableGutters>
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
        <Box display="flex" alignItems="center" gap={2} flex={1}>
          <Avatar
            variant="square"
            src={listens[0].image_thumbnail_url}
            alt={title}
            sx={{ width: 56, height: 56 }}
          />
          <Box flex={1}>
            <Typography variant="subtitle1">{title}</Typography>
            <Typography variant="body2" color="text.secondary">
              {artistNames} • {formattedDate}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Last played: {mostRecentPlay}
            </Typography>
          </Box>
          <Box display="flex" gap={1}>
            <IconButton size="small" color="primary" onClick={handlePlay}>
              <PlayArrowIcon />
            </IconButton>
            <IconButton size="small" color="primary" onClick={handleAddToQueue}>
              <QueueMusicIcon />
            </IconButton>
          </Box>
        </Box>
      </AccordionSummary>
      <AccordionDetails>
        <Table size="small">
          <TableBody>
            {listens.map((listen) => (
              <tr key={listen.playback_history_uuid}>
                <td style={{ paddingRight: "1rem" }}>
                  <Typography variant="body2">{listen.song_title}</Typography>
                </td>
                <td>
                  <Typography variant="caption" color="text.secondary">
                    {new Date(listen.played_at).toLocaleString()}
                  </Typography>
                </td>
              </tr>
            ))}
          </TableBody>
        </Table>
      </AccordionDetails>
    </Accordion>
  );
};

export default AlbumHistoryCard;
