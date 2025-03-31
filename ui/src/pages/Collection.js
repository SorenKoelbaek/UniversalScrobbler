import React, { useEffect, useState, useMemo } from "react";
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
  const [collection, setCollection] = useState(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState("album_title");
  const [sortDir, setSortDir] = useState("asc");
  const [viewMode, setViewMode] = useState("table");

  useEffect(() => {
    const fetchCollection = async () => {
      try {
        const res = await apiClient.get("/collection/");
        setCollection(res.data);
      } catch (error) {
        console.error("Failed to fetch collection:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchCollection();
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
    if (!collection?.album_releases) return [];
    return collection.album_releases
      .filter((release) => {
        const match = (str) =>
          str?.toLowerCase().includes(search.toLowerCase());
        return (
          match(release.album_title) ||
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
  }, [collection, search, sortKey, sortDir]);

  return (
    <Container maxWidth="lg" sx={{ mt: 4 }}>
      <Box
        display="flex"
        justifyContent="space-between"
        alignItems="center"
        mb={2}
      >
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
                  <TableCell sortDirection={sortKey === "album_title" ? sortDir : false}>
                    <TableSortLabel
                      active={sortKey === "album_title"}
                      direction={sortDir}
                      onClick={() => handleSort("album_title")}
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
                </TableRow>
              </TableHead>
              <TableBody>
                {filteredReleases.map((release) => (
                  <AlbumCard
                    key={release.album_release_uuid}
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
    </Container>
  );
};

export default Collection;
