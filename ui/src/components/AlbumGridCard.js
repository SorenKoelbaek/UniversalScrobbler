import React from "react";
import {
  Card,
  CardMedia,
  CardContent,
  Typography,
  Box,
  IconButton
} from "@mui/material";
import { useNavigate } from "react-router-dom";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import QueueMusicIcon from "@mui/icons-material/QueueMusic";

const AlbumGridCard = ({ albumRelease }) => {
  const {
    title,
    image_thumbnail_url,
    release_date,
    artists,
    album_uuid,
    formats
  } = albumRelease;

  const navigate = useNavigate();

    const handlePlay = (e) => {
    e.stopPropagation(); // prevent row click navigation
    console.log("Play album:", album_uuid);
  };

  const handleAddToQueue = (e) => {
    e.stopPropagation();
    console.log("Add album to queue:", album_uuid);
  };


  const artistNames = artists?.map((a) => a.name).join(", ") || "—";
  const formattedDate = release_date
    ? new Date(release_date).toLocaleDateString()
    : "—";

  return (
    <Box onClick={() => navigate(`/album/${album_uuid}`)} sx={{ cursor: "pointer" }}>
      <Card sx={{ width: 180 }}>
        <CardMedia
          component="img"
          height="150"
          image={image_thumbnail_url}
          alt={title}
          loading="lazy"
        />
        <CardContent>
          <Typography variant="body1" noWrap>
            {title}
          </Typography>
          <Typography variant="body2" color="text.secondary" noWrap>
            {artistNames}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {formattedDate}
          </Typography>
          {formats?.some(
            (f) => f.format === "digital" && f.status === "owned"
          ) && (
          <IconButton size="small" color="primary" onClick={handlePlay}>
            <PlayArrowIcon />
          </IconButton>
          )}
          {formats?.some(
            (f) => f.format === "digital" && f.status === "owned"
          ) && (
          <IconButton size="small" color="primary" onClick={handleAddToQueue}>
            <QueueMusicIcon />
          </IconButton>
           )}
        </CardContent>
      </Card>
    </Box>
  );
};

export default AlbumGridCard;
