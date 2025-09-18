// src/pages/Discover.js
import React, { useEffect, useState, useMemo } from "react";
import {
  Container,
  Typography,
  TextField,
  Box,
  ToggleButton,
  ToggleButtonGroup,
  Grid,
  CircularProgress,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TableSortLabel,
} from "@mui/material";
import apiClient from "../utils/apiClient";
import AlbumCard from "../components/AlbumCard";
import AlbumGridCard from "../components/AlbumGridCard";
import ArtistCarousel from "../components/ArtistCarousel";

const Discover = () => {
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState({ albums: [], artists: [], tracks: [] });
  const [recommended, setRecommended] = useState([]);
  const [sortKey, setSortKey] = useState("title");
  const [sortDir, setSortDir] = useState("asc");
  const [viewMode, setViewMode] = useState("table");

  // fetch recommended artists on mount
  useEffect(() => {
    const fetchRecommended = async () => {
      try {
        const res = await apiClient.get("/listen/recommended-artists");
        // 🔒 Pre-pick 2 random albums once per artist
        const withStableAlbums = res.data.map((artist) => {
          if (!artist.albums || artist.albums.length === 0) {
            return { ...artist, previewAlbums: [] };
          }
          const shuffled = [...artist.albums].sort(() => 0.5 - Math.random());
          return { ...artist, previewAlbums: shuffled.slice(0, 2) };
        });
        setRecommended(withStableAlbums);
      } catch (err) {
        console.error("Failed to fetch recommended artists:", err);
      }
    };
    fetchRecommended();
  }, []);

  // debounce input
  useEffect(() => {
    const timeout = setTimeout(() => {
      if (search.length >= 2) {
        setDebouncedSearch(search);
      } else {
        setDebouncedSearch("");
        setResults({ albums: [], artists: [], tracks: [] });
      }
    }, 300);
    return () => clearTimeout(timeout);
  }, [search]);

  // fetch search results
  useEffect(() => {
    if (!debouncedSearch) return;
    const fetchResults = async () => {
      setLoading(true);
      try {
        const res = await apiClient.get("/music/search/", {
          params: { query: debouncedSearch, only_digital: true },
        });
        setResults(res.data);
      } catch (err) {
        console.error("Search failed:", err);
      } finally {
        setLoading(false);
      }
    };
    fetchResults();
  }, [debouncedSearch]);

  // unify albums from albums + artist.albums + track.albums
  const albums = useMemo(() => {
    const seen = new Set();
    const merged = [];

    const pushAlbum = (a) => {
      if (a && !seen.has(a.album_uuid)) {
        seen.add(a.album_uuid);
        merged.push(a);
      }
    };

    results.albums.forEach(pushAlbum);
    results.artists.forEach((artist) => artist.albums?.forEach(pushAlbum));
    results.tracks.forEach((track) => track.albums?.forEach(pushAlbum));

    return merged.sort((a, b) => {
      const valA = a[sortKey];
      const valB = b[sortKey];
      if (!valA) return 1;
      if (!valB) return -1;
      return sortDir === "asc"
        ? String(valA).localeCompare(String(valB))
        : String(valB).localeCompare(String(valA));
    });
  }, [results, sortKey, sortDir]);

  const handleSort = (key) => {
    if (sortKey === key) {
      setSortDir((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  };

  return (
    <Container maxWidth="lg" sx={{ mt: 4 }}>
      {/* 🔍 Search box always visible */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
        <Typography variant="h5">Discover</Typography>
        <ToggleButtonGroup
          value={viewMode}
          exclusive
          onChange={(e, val) => val && setViewMode(val)}
          size="small"
        >
          <ToggleButton value="table">List</ToggleButton>
          <ToggleButton value="grid">Grid</ToggleButton>
        </ToggleButtonGroup>
      </Box>

      <TextField
        fullWidth
        placeholder="Search albums, artists, or tracks..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        sx={{ mb: 4 }}
      />

      {/* 🎛 Conditional content */}
      {debouncedSearch ? (
        loading ? (
          <Box display="flex" justifyContent="center" mt={4}>
            <CircularProgress />
          </Box>
        ) : albums.length === 0 ? (
          <Typography variant="body1" align="center" mt={4}>
            No results found.
          </Typography>
        ) : viewMode === "table" ? (
          <Paper>
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Cover</TableCell>
                    <TableCell></TableCell>
                    <TableCell sortDirection={sortKey === "title" ? sortDir : false}>
                      <TableSortLabel
                        active={sortKey === "title"}
                        direction={sortDir}
                        onClick={() => handleSort("title")}
                      >
                        Title
                      </TableSortLabel>
                    </TableCell>
                    <TableCell>Artist(s)</TableCell>
                    <TableCell sortDirection={sortKey === "release_date" ? sortDir : false}>
                      <TableSortLabel
                        active={sortKey === "release_date"}
                        direction={sortDir}
                        onClick={() => handleSort("release_date")}
                      >
                        Release Date
                      </TableSortLabel>
                    </TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {albums.map((album) => (
                    <AlbumCard key={album.album_uuid} albumRelease={album} />
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Paper>
        ) : (
          <Grid container spacing={2}>
            {albums.map((album) => (
              <Grid item key={album.album_uuid}>
                <AlbumGridCard albumRelease={album} />
              </Grid>
            ))}
          </Grid>
        )
      ) : (
        recommended.length > 0 && <ArtistCarousel artists={recommended} />
      )}
    </Container>
  );
};

export default Discover;
