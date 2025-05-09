import React, { useEffect, useState } from "react";
import {
  Box,
  Typography,
  Container,
  Card,
  CardContent,
  CardMedia,
  Grid,
  CircularProgress,
  Button,
  Divider,
} from "@mui/material";
import { useParams, Link } from "react-router-dom";
import apiClient from "../utils/apiClient";
import TagBubbleChart from "../components/TagBubbleChart";
import TrackList from "../components/TrackList";
import ReleaseList from "../components/ReleaseList";

const AlbumDetail = () => {
  const { album_uuid } = useParams();
  const [album, setAlbum] = useState(null);
  const [loading, setLoading] = useState(true);

  const enrichAlbumIfNeeded = async (album) => {
    if (!album.discogs_master_id && !album.discogs_main_release_id) {
      try {
        const response = await apiClient.post(`/discogs/enrich/album/${album.album_uuid}`);
        setAlbum(response.data);  // 💥 overwrite with enriched album
      } catch (err) {
        console.warn("Discogs enrichment failed:", err);
      }
    }
  };


  useEffect(() => {
    const fetchAlbum = async () => {
      try {
        const response = await apiClient.get(`/music/albums/${album_uuid}`);
        const albumData = response.data;
        setAlbum(albumData); // ✅ Set immediately so the page can render
        console.log(albumData);
        // 🔁 Lazy trigger enrichment after render, no blocking
        enrichAlbumIfNeeded(albumData);
      } catch (err) {
        console.error("Failed to fetch album:", err);
      } finally {
        setLoading(false); // ✅ Only reflects initial album load
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

              {album.discogs_master_id && (
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                  <a
                    href={`https://www.discogs.com/master/${album.discogs_master_id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ color: "#1976d2", textDecoration: "none" }}
                  >
                    View on Discogs
                  </a>
                </Typography>
              )}
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

          <Divider sx={{ my: 3 }} />

          <TrackList tracks={album.tracks} />

          <Divider sx={{ my: 3 }} />

          <ReleaseList releases={album.releases} />
        </Grid>
      </Grid>
    </Container>
  );
};

export default AlbumDetail;
