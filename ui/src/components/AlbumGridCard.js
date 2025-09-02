import React from "react";
import {
  Card,
  CardMedia,
  CardContent,
  Typography,
  Box,
} from "@mui/material";
import { useNavigate } from "react-router-dom";

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
        </CardContent>
      </Card>
    </Box>
  );
};

export default AlbumGridCard;
