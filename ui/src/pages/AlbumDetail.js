// src/pages/AlbumDetailPage.js

import React, { useEffect, useState } from "react";
import {
  Box,
  Typography,
  Container,
  Card,
  CardContent,
  CardMedia,
  Grid,
  Chip,
  Divider,
  CircularProgress,
  Button,
} from "@mui/material";
import { useParams, Link } from "react-router-dom";
import apiClient from "../utils/apiClient";
import TagBubbleChart from "../components/TagBubbleChart";

const AlbumDetail = () => {
  const { album_uuid } = useParams();
  const [album, setAlbum] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchAlbum = async () => {
      try {
        const response = await apiClient.get(`/music/albums/${album_uuid}`);
        setAlbum(response.data);
      } catch (err) {
        console.error("Failed to fetch album:", err);
      } finally {
        setLoading(false);
      }
    };
    fetchAlbum();
  }, [album_uuid]);

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" mt={6}>
        <CircularProgress />
      </Box>
    );
  }

  if (!album) {
    return (
      <Container maxWidth="md" sx={{ mt: 4 }}>
        <Typography variant="h6" align="center">
          Album not found.
        </Typography>
      </Container>
    );
  }

  const formattedReleaseDate = album.release_date
    ? new Date(album.release_date).toLocaleDateString()
    : "—";

  return (
    <Container maxWidth="md" sx={{ mt: 4, mb: 8 }}>
      <Grid container spacing={4}>
        {/* Album Artwork + Metadata */}
        <Grid item xs={12} sm={4}>
          <Card>
            <CardMedia
              component="img"
              image={album.image_url}
              alt={album.title}
              sx={{ height: 240, objectFit: "cover" }}
            />
            <CardContent>
              <Typography variant="h6">{album.title}</Typography>
              <Typography variant="subtitle2">
                {album.artists.map((artist, index) => (
                  <React.Fragment key={artist.artist_uuid}>
                    <Button
                      component={Link}
                      to={`/artist/${artist.artist_uuid}`}
                      sx={{ padding: 0, minWidth: 0, textTransform: "none" }}
                    >
                      {artist.name}
                    </Button>
                    {index < album.artists.length - 1 && ", "}
                  </React.Fragment>
                ))}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Released: {formattedReleaseDate}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Tags + Tracklist + Releases */}
        <Grid item xs={12} sm={8}>
          <Box mb={3}>
            <Typography variant="h6">Tags</Typography>
            <Box display="flex" flexWrap="wrap" gap={1} mt={1}>
              <TagBubbleChart tags={album.tags} />
            </Box>
          </Box>

          <Divider />

          <Box mt={3}>
            <Typography variant="h6" gutterBottom>
              Tracklist
            </Typography>
           {album.tracks.map((track, i) => (
            <Typography key={track.track_uuid} variant="body2">
              {i + 1}.{" "}
              <Button
                component={Link}
                to={`/track/${track.track_uuid}`}
                sx={{ padding: 0, minWidth: 0, textTransform: "none" }}
              >
                {track.name}
              </Button>
            </Typography>
          ))}

          </Box>

          <Divider sx={{ my: 3 }} />

          <Box>
            <Typography variant="h6" gutterBottom>
              Releases
            </Typography>
            {album.releases.map((rel) => (
              <Typography key={rel.album_release_uuid} variant="body2">
                {rel.release_date
                  ? new Date(rel.release_date).toLocaleDateString()
                  : "—"}{" "}
                ({rel.country || "Unknown"})
              </Typography>
            ))}
          </Box>
        </Grid>
      </Grid>
    </Container>
  );
};

export default AlbumDetail;
