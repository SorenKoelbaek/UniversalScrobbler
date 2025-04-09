import React from "react";
import { TableRow, TableCell, Avatar, Typography } from "@mui/material";
import { useInView } from "react-intersection-observer";
import { useNavigate } from "react-router-dom";

const AlbumCard = ({ albumRelease }) => {
  const {
    album_title,
    image_thumbnail_url,
    release_date,
    country,
    artists,
    album_uuid,
  } = albumRelease;

  const { ref, inView } = useInView({
    triggerOnce: true,
    rootMargin: "200px",
  });

  const navigate = useNavigate();

  const artistNames = artists?.map((a) => a.name).join(", ") || "—";
  const formattedDate = release_date
    ? new Date(release_date).toLocaleDateString()
    : "—";

  return (
    <TableRow hover onClick={() => navigate(`/album/${album_uuid}`)} style={{ cursor: "pointer" }}>
      <TableCell ref={ref}>
        {inView && (
          <Avatar
            variant="square"
            src={image_thumbnail_url}
            alt={album_title}
            sx={{ width: 56, height: 56 }}
          />
        )}
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
