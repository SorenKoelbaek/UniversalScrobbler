import React, { useEffect, useState, useMemo, useRef, useCallback } from "react";
import {
  Container,
  Typography,
  TextField,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  CircularProgress,
  TableSortLabel,
  Box,
  ToggleButton,
  ToggleButtonGroup,
  Grid,
} from "@mui/material";
import apiClient from "../utils/apiClient";
import AlbumCard from "../components/AlbumCard";
import AlbumGridCard from "../components/AlbumGridCard";

const Collection = () => {
  const [collection, setCollection] = useState({ items: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const [isFetchingMore, setIsFetchingMore] = useState(false);
  const [offset, setOffset] = useState(0);
  const [limit] = useState(100);
  const [hasMore, setHasMore] = useState(true);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [sortKey, setSortKey] = useState("title");
  const [sortDir, setSortDir] = useState("asc");
  const [viewMode, setViewMode] = useState("table");

  const fetchCollection = async (initial = false) => {
    try {
      const res = await apiClient.get("/collection/", {
        params: {
          offset,
          limit,
          search: debouncedSearch,
        },
      });

      const newItems = res.data.items;
      const total = res.data.total;

      setCollection((prev) => ({
        items: initial ? newItems : [...prev.items, ...newItems],
        total,
      }));

      setHasMore(offset + limit < total);
      setOffset((prev) => prev + limit);
    } catch (error) {
      console.error("Failed to fetch collection:", error);
    } finally {
      setLoading(false);
      setIsFetchingMore(false);
    }
    };
  useEffect(() => {
    const timeout = setTimeout(() => {
      if (search.length === 0) {
        setDebouncedSearch(""); // clears search
      } else if (search.length >= 3) {
        setDebouncedSearch(search); // triggers search
      }
    }, 100);

    return () => clearTimeout(timeout);
  }, [search]);

  useEffect(() => {
    setOffset(0);
    setHasMore(true);
    setCollection({ items: [], total: 0 });
    fetchCollection(true);  // full refresh with search term
  }, [debouncedSearch]);

  useEffect(() => {
    fetchCollection(true);
  }, []);

  const handleSort = (key) => {
    if (sortKey === key) {
      setSortDir((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  };

  const filteredReleases = useMemo(() => {
    // If using server-side search, skip client filtering
    if (debouncedSearch.length >= 3 || debouncedSearch.length === 0) {
      return collection.items.sort((a, b) => {
        const valA = a[sortKey];
        const valB = b[sortKey];
        if (!valA) return 1;
        if (!valB) return -1;
        return sortDir === "asc"
          ? valA.localeCompare(valB)
          : valB.localeCompare(valA);
      });
    }

    // Fallback: if in the middle of typing (1–2 characters), do local filtering
    return collection.items
      .filter((release) => {
        const match = (str) =>
          str?.toLowerCase().includes(search.toLowerCase());
        return (
          match(release.title) ||
          release.artists?.some((a) => match(a.name))
        );
      })
      .sort((a, b) => {
        const valA = a[sortKey];
        const valB = b[sortKey];
        if (!valA) return 1;
        if (!valB) return -1;
        return sortDir === "asc"
          ? valA.localeCompare(valB)
          : valB.localeCompare(valA);
      });
  }, [collection, search, sortKey, sortDir, debouncedSearch]);

  // Infinite scroll
  const observer = useRef();
    const sentinelRef = useCallback(
    (node) => {
      if (isFetchingMore || loading || !hasMore) return;

      if (observer.current) observer.current.disconnect();
      observer.current = new IntersectionObserver((entries) => {
        if (entries[0].isIntersecting) {
          setIsFetchingMore(true);
          fetchCollection(false);
        }
      });

      if (node) observer.current.observe(node);
    },
    [isFetchingMore, hasMore, loading, debouncedSearch]
  );


  return (
    <Container maxWidth="lg" sx={{ mt: 4 }}>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
        <Typography variant="h5">My Collection</Typography>
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
        placeholder="Search by album title or artist..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        sx={{ mb: 2 }}
      />

      {loading ? (
        <Box display="flex" justifyContent="center" mt={4}>
          <CircularProgress />
        </Box>
      ) : filteredReleases.length === 0 ? (
        <Typography variant="body1" align="center" mt={4}>
          No albums found.
        </Typography>
      ) : viewMode === "table" ? (
        <Paper>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Cover</TableCell>
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
                  <TableCell sortDirection={sortKey === "country" ? sortDir : false}>
                    <TableSortLabel
                      active={sortKey === "country"}
                      direction={sortDir}
                      onClick={() => handleSort("country")}
                    >
                      Country
                    </TableSortLabel>
                  </TableCell>
                 <TableCell sortDirection={sortKey === "formats" ? sortDir : false}>
                    <TableSortLabel
                      active={sortKey === "formats"}
                      direction={sortDir}
                      onClick={() => handleSort("formats")}
                    >
                      Formats
                    </TableSortLabel>
                  </TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {filteredReleases.map((release) => (
                  <AlbumCard
                    key={release.album_uuid}
                    albumRelease={release}
                  />
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>
      ) : (
        <Grid container spacing={2}>
          {filteredReleases.map((release) => (
            <Grid item key={release.album_release_uuid}>
              <AlbumGridCard albumRelease={release} />
            </Grid>
          ))}
        </Grid>
      )}

      {/* Sentinel for infinite scroll */}
      <div ref={sentinelRef} style={{ height: 1 }} />

      {/* Bottom loading spinner */}
      {isFetchingMore && (
        <Box display="flex" justifyContent="center" mt={2}>
          <CircularProgress size={24} />
        </Box>
      )}
    </Container>
  );
};

export default Collection;
