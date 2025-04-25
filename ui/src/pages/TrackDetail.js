// src/pages/TrackDetail.js

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
  Divider,
  Button,
} from "@mui/material";
import { useParams, Link } from "react-router-dom";
import apiClient from "../utils/apiClient";
import TagBubbleChart from "../components/TagBubbleChart";
import AlbumListTable from "../components/AlbumListTable";

const TrackDetail = () => {
  const { track_uuid } = useParams();
  const [track, setTrack] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchTrack = async () => {
      try {
        const response = await apiClient.get(`/music/tracks/${track_uuid}`);
        setTrack(response.data);
      } catch (err) {
        console.error("Failed to fetch track:", err);
      } finally {
        setLoading(false);
      }
    };
    fetchTrack();
  }, [track_uuid]);

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" mt={6}>
        <CircularProgress />
      </Box>
    );
  }

  if (!track) {
    return (
      <Container maxWidth="md" sx={{ mt: 4 }}>
        <Typography variant="h6" align="center">Track not found.</Typography>
      </Container>
    );
  }

  const aggregatedTags = {};
  track.track_versions.forEach((version) => {
    version.tags.forEach((tag) => {
      if (!aggregatedTags[tag.tag_uuid]) {
        aggregatedTags[tag.tag_uuid] = { ...tag };
      } else {
        aggregatedTags[tag.tag_uuid].count += tag.count;
      }
    });
  });

  return (
    <Container maxWidth="md" sx={{ mt: 4, mb: 8 }}>
      <Grid container spacing={4}>
        {/* Track info */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h5" gutterBottom>{track.name}</Typography>
              <Typography variant="subtitle2">
                {track.artists.map((artist, index) => (
                  <React.Fragment key={artist.artist_uuid}>
                    <Button
                      component={Link}
                      to={`/artist/${artist.artist_uuid}`}
                      sx={{ padding: 0, minWidth: 0, textTransform: "none" }}
                    >
                      {artist.name}
                    </Button>
                    {index < track.artists.length - 1 && ", "}
                  </React.Fragment>
                ))}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Tags */}
        <Grid item xs={12}>
          <Typography variant="h6">Tags</Typography>
          <Box display="flex" flexWrap="wrap" gap={1} mt={1}>
            <TagBubbleChart tags={Object.values(aggregatedTags)} />
          </Box>
        </Grid>

        {/* Appears on Albums */}
        <Grid item xs={12}>
          <Typography variant="h6" gutterBottom>Appears on Albums</Typography>
          <>
            <AlbumListTable albums={track.albums} showArtist={true} />
          </>


        </Grid>

        {/* Track Versions */}
        <Grid item xs={12}>
          <Divider sx={{ my: 2 }} />
          <Typography variant="h6" gutterBottom>Track Versions</Typography>
          {track.track_versions.map((version, index) => (
            <Box key={version.track_version_uuid} mb={2}>
              <Typography variant="subtitle2">
                Version {index + 1} — Duration: {Math.round((version.duration || 0) / 1000)} sec
              </Typography>
              <Typography variant="body2">
                Releases:{" "}
                {version.album_releases.map((rel, i) => (
                  <span key={rel.album_release_uuid}>
                    {rel.title} ({rel.country || "Unknown"}, {rel.release_date ? new Date(rel.release_date).getFullYear() : "—"})
                    {i < version.album_releases.length - 1 && ", "}
                  </span>
                ))}
              </Typography>
            </Box>
          ))}
        </Grid>
      </Grid>
    </Container>
  );
};

export default TrackDetail;
