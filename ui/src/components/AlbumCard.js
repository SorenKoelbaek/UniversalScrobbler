import React from "react";
import { TableRow, TableCell, Avatar, Typography, Box } from "@mui/material";

const AlbumCard = ({ albumRelease }) => {
  const {
    album_title,
    image_thumbnail_url,
    release_date,
    country,
    artists,
  } = albumRelease;

  const artistNames = artists?.map((a) => a.name).join(", ") || "—";

  const formattedDate = release_date
    ? new Date(release_date).toLocaleDateString()
    : "—";

  return (
    <TableRow hover>
      <TableCell>
        <Avatar
          variant="square"
          src={image_thumbnail_url}
          alt={album_title}
          sx={{ width: 56, height: 56 }}
          loading="lazy"
        />
      </TableCell>
      <TableCell>
        <Typography variant="body1">{album_title}</Typography>
      </TableCell>
      <TableCell>{artistNames}</TableCell>
      <TableCell>{formattedDate}</TableCell>
      <TableCell>{country || "—"}</TableCell>
    </TableRow>
  );
};

export default AlbumCard;
