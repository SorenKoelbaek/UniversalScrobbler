import React from "react";
import { Grid, Container } from "@mui/material";
import TrackCountBarChart from "../components/TrackCountBarChart";
import TopTracksCard from "../components/TopTracksCard";

const Dashboard = () => {
  return (
    <Container maxWidth="lg" sx={{ mt: 4 }}>
      <Grid container spacing={2}>
        <Grid item xs={12} sm={6} md={4}>
          <TrackCountBarChart />
        </Grid>
        <Grid item xs={12} sm={6} md={4}>
          <TopTracksCard />
        </Grid>
        <Grid item xs={12} sm={6} md={4}>
          <div style={{ background: "#f0f0f0", padding: "1rem" }}>Tile 3</div>
        </Grid>
        <Grid item xs={12} sm={6} md={4}>
          <div style={{ background: "#f0f0f0", padding: "1rem" }}>Tile 4</div>
        </Grid>
        <Grid item xs={12} sm={6} md={4}>
          <div style={{ background: "#f0f0f0", padding: "1rem" }}>Tile 5</div>
        </Grid>
        <Grid item xs={12} sm={6} md={4}>
          <div style={{ background: "#f0f0f0", padding: "1rem" }}>Tile 6</div>
        </Grid>
      </Grid>
    </Container>
  );
};

export default Dashboard;
