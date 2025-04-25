import React from "react";
import {
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  Typography,
  Divider,
} from "@mui/material";
import { useNavigate } from "react-router-dom";

const ArtistListTable = ({ artists = [] }) => {
  const navigate = useNavigate();

  if (artists.length === 0) {
    return null; // or return a placeholder
  }

  return (
    <>
      <Typography variant="h6" gutterBottom>
        Artists
      </Typography>
      <List dense>
        {artists.map((artist, index) => (
          <React.Fragment key={artist.artist_uuid}>
            <ListItem disablePadding>
              <ListItemButton onClick={() => navigate(`/artist/${artist.artist_uuid}`)}>
                <ListItemText primary={artist.name} />
              </ListItemButton>
            </ListItem>
            {index < artists.length - 1 && <Divider component="li" />}
          </React.Fragment>
        ))}
      </List>
    </>
  );
};


export default ArtistListTable;
