import React from "react";
import { Card, CardContent, Typography, CardActionArea } from "@mui/material";
import { useNavigate } from "react-router-dom";

const ArtistCard = ({ artist }) => {
  const navigate = useNavigate();

  return (
    <Card sx={{ width: 200, height: 100 }}>
      <CardActionArea onClick={() => navigate(`/artist/${artist.artist_uuid}`)}>
        <CardContent>
          <Typography variant="body1" noWrap>
            {artist.name}
          </Typography>
        </CardContent>
      </CardActionArea>
    </Card>
  );
};

export default ArtistCard;