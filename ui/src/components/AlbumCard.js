import React from "react";
import { TableRow, TableCell, Avatar, Typography } from "@mui/material";
import { useInView } from "react-intersection-observer";
import { useNavigate } from "react-router-dom";
import AlbumIcon from "@mui/icons-material/Album";       // vinyl record
import ComputerIcon from "@mui/icons-material/Computer"; // digital
import MusicNoteIcon from "@mui/icons-material/MusicNote"; // alt digital

const AlbumCard = ({ albumRelease }) => {
  const {
    title,
    image_thumbnail_url,
    release_date,
    country,
    artists,
    album_uuid,
    formats,
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
            alt={title}
            sx={{ width: 56, height: 56 }}
          />
        )}
      </TableCell>
      <TableCell>
        <Typography variant="body1">{title}</Typography>
      </TableCell>
      <TableCell>{artistNames}</TableCell>
      <TableCell>{formattedDate}</TableCell>
      <TableCell>{country || "—"}</TableCell>
      <TableCell>
          {formats?.map((f, idx) => {
            const isOwned = f.status === "owned";
            const iconColor = isOwned ? "primary" : "disabled";
            // "primary" → blue (theme), "disabled" → greyed-out

            switch (f.format.toLowerCase()) {
              case "vinyl":
                return <AlbumIcon key={idx} color={iconColor} sx={{ mr: 1 }} />;
              case "digital":
                return <ComputerIcon key={idx} color={iconColor} sx={{ mr: 1 }} />;
              default:
                return <MusicNoteIcon key={idx} color={iconColor} sx={{ mr: 1 }} />;
            }
          })}
        </TableCell>
    </TableRow>
  );
};

export default AlbumCard;
