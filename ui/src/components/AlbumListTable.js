import React from "react";
import {
  Box,
  Typography,
  List,
  ListItem,
  ListItemText,
  Divider,
  Link as MuiLink,
} from "@mui/material";
import { Link } from "react-router-dom";

// Preferred type sort order
const TYPE_ORDER = [
  "Album", "EP", "Single", "Live", "Remix", "DJ-mix", "Compilation", "Mixtape/Street",
  "Soundtrack", "Interview", "Spokenword", "Audiobook", "Audio drama", "Field recording", "Demo", "Broadcast", "Other"
];

function calculateTypeGroup(album) {
  if (!album.types || album.types.length === 0) return "(Other)";
  const names = album.types.map((t) => t.name).sort();
  return `(${names.join(", ")})`;
}

function calculateSortValue(album) {
  if (!album.types || album.types.length === 0) return 999;
  return album.types.reduce((acc, t) => {
    const idx = TYPE_ORDER.indexOf(t.name);
    return acc + (idx >= 0 ? idx + 1 : 999); // +1 to make Album = 1
  }, 0);
}

const AlbumListTable = ({ albums, showArtist = false }) => {
  if (!albums || albums.length === 0) return null;

  // Build albums grouped by typeGroup
  const grouped = {};
  albums.forEach((album) => {
    const typeGroup = calculateTypeGroup(album);
    const sortKey = calculateSortValue(album);
    if (!grouped[typeGroup]) grouped[typeGroup] = { albums: [], sortKey };
    grouped[typeGroup].albums.push(album);
  });

  // Sort groups by summed sortKey
  const sortedGroups = Object.entries(grouped).sort((a, b) => a[1].sortKey - b[1].sortKey);

  return (
    <Box>
      {sortedGroups.map(([typeGroup, { albums }]) => (
        <Box key={typeGroup} sx={{ mb: 4 }}>
          <Typography variant="subtitle1" sx={{ fontWeight: "bold", mt: 3, mb: 1 }}>
            {typeGroup}
          </Typography>
          <List disablePadding>
            {albums
              .sort((a, b) => {
                const dateA = a.release_date ? new Date(a.release_date) : null;
                const dateB = b.release_date ? new Date(b.release_date) : null;
                if (dateA && dateB) return dateA - dateB;
                if (dateA) return -1;
                if (dateB) return 1;
                return a.title.localeCompare(b.title);
              })
              .map((album) => (
                <React.Fragment key={album.album_uuid}>
                  <ListItem
                    component={Link}
                    to={`/album/${album.album_uuid}`}
                    sx={{
                      px: 0,
                      py: 1,
                      display: "flex",
                      justifyContent: "space-between",
                      borderBottom: "1px solid #eee",
                    }}
                  >
                    <ListItemText
                      primary={
                        <Typography variant="body1" color="primary">
                          {album.title}
                        </Typography>
                      }
                      secondary={
                        showArtist && album.artists && album.artists.length > 0
                          ? album.artists.map((a) => a.name).join(", ")
                          : null
                      }
                    />
                    <Typography variant="body2" sx={{ minWidth: 100, textAlign: "right" }}>
                      {album.release_date
                        ? new Date(album.release_date).toLocaleDateString()
                        : "—"}
                    </Typography>
                  </ListItem>
                </React.Fragment>
              ))}
          </List>
        </Box>
      ))}
    </Box>
  );
};

export default AlbumListTable;