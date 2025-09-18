// src/components/AlbumCarouselCard.js
import React from "react";
import {
  Card,
  CardMedia,
  CardContent,
  Typography,
  Box,
  IconButton,
} from "@mui/material";
import { useNavigate } from "react-router-dom";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import apiClient from "../utils/apiClient";

const CARD_WIDTH = 140;
const CARD_HEIGHT = 200;

const AlbumCarouselCard = ({ album }) => {
  const { title, image_thumbnail_url, release_date, album_uuid } = album;
  const navigate = useNavigate();

  const handlePlay = async (e) => {
    e.stopPropagation();
    try {
      await apiClient.post("/playback-sessions/play", { album_uuid });
      console.log("▶️ Play requested:", album_uuid);
    } catch (err) {
      console.error("❌ Failed to start playback", err);
    }
  };

  const year = release_date ? new Date(release_date).getFullYear() : "—";

  return (
    <Card
      onClick={() => navigate(`/album/${album_uuid}`)}
      sx={{
        width: CARD_WIDTH,
        height: CARD_HEIGHT,
        position: "relative",
        cursor: "pointer",
        overflow: "hidden",
        boxShadow: 2,
        "&:hover .hover-overlay": { opacity: 1 },
      }}
    >
      {/* Album art */}
      <Box sx={{ position: "relative", width: "100%", height: 140 }}>
        <CardMedia
          component="img"
          image={
            image_thumbnail_url ||
            "https://via.placeholder.com/140?text=No+Cover"
          }
          alt={title}
          sx={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
          }}
        />

        {/* Always render hover overlay */}
        <Box
          className="hover-overlay"
          sx={{
            position: "absolute",
            inset: 0,
            bgcolor: "rgba(0,0,0,0.5)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            opacity: 0,
            transition: "opacity 0.2s ease-in-out",
          }}
        >
          <IconButton
            size="large"
            sx={{ color: "white" }}
            onClick={handlePlay}
          >
            <PlayArrowIcon fontSize="large" />
          </IconButton>
        </Box>
      </Box>

      {/* Title + Year */}
      <CardContent sx={{ p: 1, height: 60 }}>
        <Typography variant="body2" noWrap fontWeight={500}>
          {title}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          {year}
        </Typography>
      </CardContent>
    </Card>
  );
};

export default AlbumCarouselCard;
