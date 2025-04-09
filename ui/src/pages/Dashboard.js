import React, { useContext } from "react";
import { Grid, Container, Card, CardContent, Typography } from "@mui/material";
import TrackCountBarChart from "../components/TrackCountBarChart";
import TopTracksCard from "../components/TopTracksCard";
import LiveSessionCard from "../components/LiveSessionCard";
import AuthContext from "../auth/AuthContext";


const Dashboard = () => {
  const { auth } = useContext(AuthContext);

  return (
    <Container maxWidth="lg" sx={{ mt: 4 }}>
      <Grid container spacing={2}>
        <Grid item xs={12} sm={6} md={4}>
          <Card>
            <CardContent>
              <TrackCountBarChart />
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={4}>
          <Card>

          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={4}>
          <Card>
            <CardContent>

            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Tile 4
              </Typography>
              <Typography>More placeholder content.</Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Tile 5
              </Typography>
              <Typography>Yet more content to come...</Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Tile 6
              </Typography>
              <Typography>Future ideas live here 👀</Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Container>
  );
};

export default Dashboard;
