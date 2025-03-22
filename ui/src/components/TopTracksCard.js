import React, { useEffect, useState } from "react";
import { Card, CardContent, Typography, List, ListItem, ListItemText, CircularProgress } from "@mui/material";
import apiClient from "../utils/apiClient";

const TopTracksCard = () => {
  const [tracks, setTracks] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchTopTracks = async () => {
      try {
        const res = await apiClient.get("/consumption/top-tracks?days=7");
        setTracks(res.data);
      } catch (error) {
        console.error("Failed to fetch top tracks:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchTopTracks();
  }, []);

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Top Tracks (Last 7 Days)
        </Typography>
        {loading ? (
          <CircularProgress />
        ) : (
          <List dense>
            {tracks.map((track, index) => (
              <ListItem key={index} disablePadding>
                <ListItemText
                  primary={`${track.track_name} — ${track.artist_name}`}
                  secondary={`Album: ${track.album_name} · Plays: ${track.play_count}`}
                />
              </ListItem>
            ))}
          </List>
        )}
      </CardContent>
    </Card>
  );
};

export default TopTracksCard;
