import React from "react";
import {
  Box,
  Typography,
  Card,
  CardMedia,
  CardContent,
  Button,
  Divider,
} from "@mui/material";
import { Link } from "react-router-dom";

// ArtistCarousel expects: [{ artist_uuid, name, profile, albums: [...] }]
const ArtistCarousel = ({ artists }) => {
  if (!artists || artists.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
        No recommendations found.
      </Typography>
    );
  }

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
        {artists.map((artist) => (
          <Box
            key={artist.artist_uuid}
            sx={{
              minWidth: 300,
              flex: "0 0 auto",
            }}
          >
            <Card sx={{ height: "100%", display: "flex", flexDirection: "column" }}>
              <CardContent>
                <Typography variant="h6" component={Link}
                  to={`/artist/${artist.artist_uuid}`}
                  sx={{ textDecoration: "none", color: "inherit" }}
                >
                  {artist.name}
                </Typography>
                {artist.profile && (
                  <Typography variant="body2" color="text.secondary">
                    {artist.profile}
                  </Typography>
                )}
              </CardContent>

              {/* Album scroll inside artist card */}
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
                {artist.albums
                  .sort(
                    (a, b) =>
                      new Date(a.release_date || "1900") -
                      new Date(b.release_date || "1900")
                  )
                  .map((album) => (
                    <Card
                      key={album.album_uuid}
                      component={Link}
                      to={`/album/${album.album_uuid}`}
                      sx={{
                        minWidth: 120,
                        flex: "0 0 auto",
                        textDecoration: "none",
                      }}
                    >
                      <CardMedia
                        component="img"
                        height="140"
                        image={
                          album.image_thumbnail_url ||
                          "https://via.placeholder.com/140?text=No+Cover"
                        }
                        alt={album.title}
                      />
                      <CardContent sx={{ p: 1 }}>
                        <Typography
                          variant="body2"
                          noWrap
                          title={album.title}
                          sx={{ fontWeight: 500 }}
                        >
                          {album.title}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {album.release_date
                            ? new Date(album.release_date).getFullYear()
                            : "—"}
                        </Typography>
                      </CardContent>
                    </Card>
                  ))}
              </Box>
            </Card>
          </Box>
        ))}
      </Box>
    </Box>
  );
};

export default ArtistCarousel;
