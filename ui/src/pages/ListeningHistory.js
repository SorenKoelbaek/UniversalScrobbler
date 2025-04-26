import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  Container,
  Typography,
  Box,
  CircularProgress,
} from "@mui/material";
import apiClient from "../utils/apiClient";
import PlaybackTrackList from "../components/PlaybackTrackList";

const ListeningHistory = () => {
  const [plays, setPlays] = useState([]);
  const [offset, setOffset] = useState(0);
  const [limit] = useState(100);
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(true);
  const [isFetchingMore, setIsFetchingMore] = useState(false);

  const fetchPlays = async (initial = false) => {
    try {
      const res = await apiClient.get("/consumption/history", {
        params: { offset, limit },
      });

      const newItems = res.data.items || [];
      const total = res.data.total || 0;

      setPlays((prev) => (initial ? newItems : [...prev, ...newItems]));
      setHasMore(offset + limit < total);
      setOffset((prev) => prev + limit);
    } catch (error) {
      console.error("Failed to fetch playback history:", error);
    } finally {
      setLoading(false);
      setIsFetchingMore(false);
    }
  };

  useEffect(() => {
    fetchPlays(true);
  }, []);

  // Infinite scroll
  const observer = useRef();
  const sentinelRef = useCallback((node) => {
  if (isFetchingMore || !hasMore || loading) return; // <-- this!

  if (observer.current) observer.current.disconnect();
  observer.current = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting) {
      setIsFetchingMore(true);
      fetchPlays(false);
    }
  });

  if (node) observer.current.observe(node);
}, [isFetchingMore, hasMore, loading]);

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
          <PlaybackTrackList plays={plays} />
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
