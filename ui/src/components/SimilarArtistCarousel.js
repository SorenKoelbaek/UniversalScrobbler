// src/components/SimilarArtistCarousel.js
import React from "react";
import { Box, Typography } from "@mui/material";
import AlbumCarouselCard from "./AlbumCarouselCard";

const SimilarArtistCarousel = ({ albums }) => {
  if (!albums || albums.length === 0) {
    return null;
  }

  return (
    <Box mt={4}>
      <Typography variant="h6" gutterBottom>
        Also Explore:
      </Typography>

      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: "repeat(5, 1fr)", // fixed 5 columns
          gap: 2,
        }}
      >
        {albums.map((album) => (
          <AlbumCarouselCard key={album.album_uuid} album={album} />
        ))}
      </Box>
    </Box>
  );
};

export default SimilarArtistCarousel;
