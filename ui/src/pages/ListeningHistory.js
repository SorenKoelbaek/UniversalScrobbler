import React, { useState, useEffect, useRef, useCallback, useMemo } from "react";
import {
  Container,
  Typography,
  Box,
  CircularProgress,
} from "@mui/material";
import apiClient from "../utils/apiClient";
import AlbumHistoryCard from "../components/AlbumHistoryCard";

const ListeningHistory = () => {
  const [plays, setPlays] = useState([]);
  const [offset, setOffset] = useState(0);
  const [limit] = useState(100);
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(true);
  const [isFetchingMore, setIsFetchingMore] = useState(false);

  const fetchPlays = async (initial = false) => {
    try {
      const res = await apiClient.get("/listen", { params: { limit, offset } });
      const newItems = res.data || [];
      setPlays((prev) => (initial ? newItems : [...prev, ...newItems]));
      setHasMore(newItems.length === limit);
      setOffset((prev) => prev + limit);
    } catch (error) {
      console.error("Failed to fetch listening history:", error);
    } finally {
      setLoading(false);
      setIsFetchingMore(false);
    }
  };

  useEffect(() => {
    fetchPlays(true);
  }, []);

  // infinite scroll sentinel
  const observer = useRef();
  const sentinelRef = useCallback(
    (node) => {
      if (isFetchingMore || !hasMore || loading) return;
      if (observer.current) observer.current.disconnect();
      observer.current = new IntersectionObserver((entries) => {
        if (entries[0].isIntersecting) {
          setIsFetchingMore(true);
          fetchPlays(false);
        }
      });
      if (node) observer.current.observe(node);
    },
    [isFetchingMore, hasMore, loading]
  );

  // group plays by album
  const grouped = useMemo(() => {
    const groups = {};
    for (const listen of plays) {
      if (!groups[listen.album_uuid]) {
        groups[listen.album_uuid] = [];
      }
      groups[listen.album_uuid].push(listen);
    }
    return Object.entries(groups)
      .map(([album_uuid, listens]) => ({
        album_uuid,
        listens: listens.sort(
          (a, b) => new Date(b.played_at) - new Date(a.played_at)
        ),
      }))
      .sort(
        (a, b) =>
          new Date(b.listens[0].played_at) - new Date(a.listens[0].played_at)
      );
  }, [plays]);

  return (
    <Container maxWidth="lg" sx={{ mt: 4 }}>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
        <Typography variant="h5">Listening History</Typography>
      </Box>

      {loading ? (
        <Box display="flex" justifyContent="center" mt={4}>
          <CircularProgress />
        </Box>
      ) : (
        <>
          {grouped.map(({ album_uuid, listens }) => (
            <AlbumHistoryCard key={album_uuid} listens={listens} />
          ))}
          <div ref={sentinelRef} style={{ height: 1 }} />
          {isFetchingMore && (
            <Box display="flex" justifyContent="center" mt={2}>
              <CircularProgress size={24} />
            </Box>
          )}
        </>
      )}
    </Container>
  );
};

export default ListeningHistory;
