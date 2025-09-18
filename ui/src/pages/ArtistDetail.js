// src/pages/ArtistDetail.js
import React, { useEffect, useState, useMemo } from "react";
import {
  Box,
  Typography,
  Container,
  Card,
  CardContent,
  Link,
  CircularProgress,
  Divider,
} from "@mui/material";
import { useParams } from "react-router-dom";
import apiClient from "../utils/apiClient";
import TagBubbleChart from "../components/TagBubbleChart";
import SimilarArtistCarousel from "../components/SimilarArtistCarousel";
import AlbumCarouselCard from "../components/AlbumCarouselCard";

const ArtistDetail = () => {
  const { artist_uuid } = useParams();
  const [artist, setArtist] = useState(null);
  const [similarAlbums, setSimilarAlbums] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadingSimilar, setLoadingSimilar] = useState(true);

  // fetch artist info
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

  // fetch similar artists → pick their albums
 useEffect(() => {
  const fetchSimilar = async () => {
    setLoadingSimilar(true);
    try {
      const response = await apiClient.get(
        `/music/artists/${artist_uuid}/similar`
      );
      const recs = response.data || [];

      const seen = new Set();
      const albums = [];

      // take max 2 albums per artist from top 5
      recs.slice(0, 5).forEach((sim) => {
        sim.albums?.slice(0, 2).forEach((a) => {
          if (!seen.has(a.album_uuid)) {
            seen.add(a.album_uuid);
            albums.push(a);
          }
        });
      });

      setSimilarAlbums(albums);
    } catch (err) {
      console.error("Failed to fetch similar artists:", err);
    } finally {
      setLoadingSimilar(false);
    }
  };
  fetchSimilar();
}, [artist_uuid]);

  // ✅ sort artist albums by release_date (oldest first)
  const sortedAlbums = useMemo(() => {
    if (!artist?.albums) return [];
    return [...artist.albums].sort((a, b) => {
      const dateA = a.release_date ? new Date(a.release_date) : null;
      const dateB = b.release_date ? new Date(b.release_date) : null;
      if (!dateA && !dateB) return 0;
      if (!dateA) return 1;
      if (!dateB) return -1;
      return dateA - dateB; // oldest first
    });
  }, [artist]);

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

      {/* Album Grid */}
      <Typography variant="h6" gutterBottom>
        Albums
      </Typography>
      {sortedAlbums.length > 0 ? (
        <Box
          sx={{
            display: "grid",
            gridTemplateColumns: "repeat(5, 1fr)", // 5 across
            gap: 2,
          }}
        >
          {sortedAlbums.map((album) => (
            <AlbumCarouselCard key={album.album_uuid} album={album} />
          ))}
        </Box>
      ) : (
        <Typography variant="body2" color="text.secondary">
          No albums found for this artist.
        </Typography>
      )}

      <Divider sx={{ my: 3 }} />

      {/* Similar Albums */}
      {loadingSimilar ? (
        <Box display="flex" justifyContent="center" mt={2}>
          <CircularProgress size={24} />
        </Box>
      ) : (
        similarAlbums.length > 0 && (
          <SimilarArtistCarousel albums={similarAlbums} />
        )
      )}
    </Container>
  );
};

export default ArtistDetail;
