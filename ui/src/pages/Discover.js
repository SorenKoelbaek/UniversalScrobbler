import React, { useState, useEffect, useCallback } from "react";
import {
  Container,
  TextField,
  Typography,
  Grid,
  CircularProgress,
  Box,
} from "@mui/material";
import { useSearchParams } from "react-router-dom";
import AlbumGridCard from "../components/AlbumGridCard";
import AlbumListTable from "../components/AlbumListTable";
import ArtistCard from "../components/ArtistCard";
import apiClient from "../utils/apiClient";
import ArtistListTable from "../components/ArtistListTable";

const Discover = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const querySearch = searchParams.get("search") || "";

  const [search, setSearch] = useState(querySearch);
  const [debouncedSearch, setDebouncedSearch] = useState(querySearch);
  const [loading, setLoading] = useState(false);
  const [albums, setAlbums] = useState([]);
  const [artists, setArtists] = useState([]);

  const fetchResults = useCallback(async () => {
    if (debouncedSearch.length < 3) {
      setAlbums([]);
      setArtists([]);
      return;
    }

    setLoading(true);
    try {
      const [albumsRes, artistsRes] = await Promise.all([
        apiClient.get("/music/albums", {
          params: { search: debouncedSearch, limit: 25 },
        }),
        apiClient.get("/music/artists", {
          params: { search: debouncedSearch, limit: 25 },
        }),
      ]);

      setAlbums(albumsRes.data.items || []);
      setArtists(artistsRes.data.items || []);
    } catch (err) {
      console.error("Discover search failed:", err);
    } finally {
      setLoading(false);
    }
  }, [debouncedSearch]);

  useEffect(() => {
    const timeout = setTimeout(() => {
      if (search.length === 0) {
        setSearchParams({});
        setDebouncedSearch("");
        setAlbums([]);
        setArtists([]);
      } else if (search.length >= 3) {
        setSearchParams({ search });
        setDebouncedSearch(search);
      }
    }, 300);

    return () => clearTimeout(timeout);
  }, [search, setSearchParams]);

  useEffect(() => {
    fetchResults();
  }, [debouncedSearch, fetchResults]);

  return (
    <Container maxWidth="lg" sx={{ mt: 4 }}>
      <TextField
        fullWidth
        placeholder="Search albums or artists..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        sx={{ mb: 4 }}
      />

      {loading ? (
        <Box display="flex" justifyContent="center" mt={4}>
          <CircularProgress />
        </Box>
      ) : (
        <>
          {albums.length > 0 && (
            <>
              <Typography variant="h6" gutterBottom>
                Albums
              </Typography>
              <AlbumListTable albums={albums} showArtist={true} />
            </>
          )}

          {artists.length > 0 && (
            <>
              <Typography variant="h6" gutterBottom>
                Artists
              </Typography>
              <ArtistListTable artists={artists} />
            </>
          )}
        </>
      )}
    </Container>
  );
};

export default Discover;
