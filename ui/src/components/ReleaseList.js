import React from "react";
import {
  Box,
  Typography,
  List,
  ListItem,
  ListItemText,
  Chip,
  Link as MuiLink,
} from "@mui/material";
import OpenInNewIcon from "@mui/icons-material/OpenInNew"; // Discogs-like external link icon

const ReleaseList = ({ releases }) => {
  if (!releases || releases.length === 0) return null;

  const sorted = [...releases].sort((a, b) => {
    const aDate = a.release_date ? new Date(a.release_date) : null;
    const bDate = b.release_date ? new Date(b.release_date) : null;
    if (aDate && bDate) return aDate - bDate;
    if (aDate) return -1;
    if (bDate) return 1;
    return 0;
  });

  return (
    <Box>
      <Typography variant="h6" gutterBottom>
        Releases
      </Typography>
      <List disablePadding>
        {sorted.map((rel) => (
          <ListItem key={rel.album_release_uuid} disablePadding sx={{ py: 0.5 }}>
            <ListItemText
              primary={
                <Typography variant="body2" component="span">
                  {rel.release_date
                    ? new Date(rel.release_date).toLocaleDateString()
                    : "—"}{" "}
                  • <strong>{rel.title || "Untitled"}</strong>{" "}
                  {rel.discogs_release_id && (
                    <MuiLink
                      href={`https://www.discogs.com/release/${rel.discogs_release_id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      sx={{ ml: 1, verticalAlign: "middle" }}
                      title="View on Discogs"
                    >
                      <OpenInNewIcon fontSize="small" />
                    </MuiLink>
                  )}
                </Typography>
              }
              secondary={
                rel.country && (
                  <Chip
                    label={rel.country}
                    size="small"
                    sx={{ mt: 0.5 }}
                    variant="outlined"
                  />
                )
              }
            />
          </ListItem>
        ))}
      </List>
    </Box>
  );
};

export default ReleaseList;
