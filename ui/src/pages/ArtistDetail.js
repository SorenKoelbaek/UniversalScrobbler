// src/pages/ArtistDetail.js

import React, { useEffect, useState } from "react";
import {
  Box,
  Typography,
  Container,
  Card,
  CardContent,
  Link,
  CircularProgress,
  Button,
  Divider,
} from "@mui/material";
import { useParams } from "react-router-dom";
import apiClient from "../utils/apiClient";
import AlbumListTable from "../components/AlbumListTable";
import TagBubbleChart from "../components/TagBubbleChart";

const ArtistDetail = () => {
  const { artist_uuid } = useParams();
  const [artist, setArtist] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchArtist = async () => {
      try {
        const response = await apiClient.get(`/music/artists/${artist_uuid}`);
        setArtist(response.data);
      } catch (err) {
        console.error("Failed to fetch artist:", err);
      } finally {
        setLoading(false);
      }
    };
    fetchArtist();
  }, [artist_uuid]);

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" mt={6}>
        <CircularProgress />
      </Box>
    );
  }

  if (!artist) {
    return (
      <Container maxWidth="md" sx={{ mt: 4 }}>
        <Typography variant="h6" align="center">
          Artist not found.
        </Typography>
      </Container>
    );
  }

  return (
    <Container maxWidth="md" sx={{ mt: 4, mb: 8 }}>
      {/* Artist Card */}
      <Card>
        <CardContent>
          <Typography variant="h4" gutterBottom>
            {artist.name}
          </Typography>
          {artist.discogs_artist_id && (
            <Typography variant="body2" mb={2}>
              <Link
                href={`https://www.discogs.com/artist/${artist.discogs_artist_id}`}
                target="_blank"
                rel="noopener noreferrer"
              >
                View on Discogs
              </Link>
            </Typography>
          )}
          {artist.profile && (
            <Typography variant="body2" color="text.secondary">
              {artist.profile}
            </Typography>
          )}
        </CardContent>
      </Card>

      {/* Tag Bubble Chart */}
      {artist.tags && artist.tags.length > 0 && (
        <Box mt={4}>
          <Typography variant="h6">Tags</Typography>
          <Box display="flex" flexWrap="wrap" gap={1} mt={1}>
            <TagBubbleChart tags={artist.tags} />
          </Box>
        </Box>
      )}

      <Divider sx={{ my: 3 }} />

      {/* Album List */}
      <Typography variant="h6" gutterBottom>
        Albums
      </Typography>
      <AlbumListTable albums={artist.albums} />
    </Container>
  );
};

export default ArtistDetail;
