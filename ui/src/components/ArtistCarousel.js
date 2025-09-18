// src/components/ArtistCarousel.js
import React from "react";
import {
  Box,
  Typography,
  Card,
  CardContent,
  Divider,
} from "@mui/material";
import { Link } from "react-router-dom";
import AlbumCarouselCard from "./AlbumCarouselCard";

// ArtistCarousel expects: [{ artist_uuid, name, profile, albums: [...], previewAlbums: [...] }]
const ArtistCarousel = ({ artists }) => {
  if (!artists || artists.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
        No recommendations found.
      </Typography>
    );
  }

  // helper: pick random N albums (fallback only)
  const pickRandomAlbums = (albums, n) => {
    if (!albums || albums.length === 0) return [];
    const shuffled = [...albums].sort(() => 0.5 - Math.random());
    return shuffled.slice(0, n);
  };

  return (
    <Box sx={{ mt: 4 }}>
      <Typography variant="h5" gutterBottom>
        Recommended Artists
      </Typography>
      <Divider sx={{ mb: 2 }} />

      <Box
        sx={{
          display: "flex",
          gap: 3,
          overflowX: "auto",
          pb: 2,
          "&::-webkit-scrollbar": { display: "none" },
        }}
      >
        {artists.slice(0, 5).map((artist) => {
          // ✅ Use pre-picked preview albums if available
          const previewAlbums =
            artist.previewAlbums && artist.previewAlbums.length > 0
              ? artist.previewAlbums
              : pickRandomAlbums(artist.albums, 2);

          return (
            <Box
              key={artist.artist_uuid}
              sx={{
                minWidth: 280,
                flex: "0 0 auto",
              }}
            >
              <Card
                sx={{
                  height: "100%",
                  display: "flex",
                  flexDirection: "column",
                  borderRadius: 2,
                  transition: "transform 0.2s",
                  "&:hover": { transform: "scale(1.02)" },
                }}
              >
                <CardContent>
                  <Typography
                    variant="h6"
                    component={Link}
                    to={`/artist/${artist.artist_uuid}`}
                    sx={{ textDecoration: "none", color: "inherit" }}
                  >
                    {artist.name}
                  </Typography>
                  {artist.profile && (
                    <Typography
                      variant="body2"
                      color="text.secondary"
                      noWrap
                      title={artist.profile}
                    >
                      {artist.profile}
                    </Typography>
                  )}
                </CardContent>

                {/* Album preview inside artist card */}
                <Box
                  sx={{
                    display: "flex",
                    gap: 2,
                    overflowX: "auto",
                    px: 2,
                    pb: 2,
                    "&::-webkit-scrollbar": { display: "none" },
                  }}
                >
                  {previewAlbums.map((album) => (
                    <AlbumCarouselCard key={album.album_uuid} album={album} />
                  ))}
                </Box>
              </Card>
            </Box>
          );
        })}
      </Box>
    </Box>
  );
};

export default ArtistCarousel;
