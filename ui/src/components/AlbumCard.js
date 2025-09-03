import React from "react";
import { TableRow, TableCell, Avatar, Typography, IconButton, Box } from "@mui/material";
import { useInView } from "react-intersection-observer";
import { useNavigate } from "react-router-dom";
import AlbumIcon from "@mui/icons-material/Album";       // vinyl record
import ComputerIcon from "@mui/icons-material/Computer"; // digital
import MusicNoteIcon from "@mui/icons-material/MusicNote"; // alt digital
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import QueueMusicIcon from "@mui/icons-material/QueueMusic";

const AlbumCard = ({ albumRelease }) => {
  const {
    title,
    image_thumbnail_url,
    release_date,
    country,
    artists,
    album_uuid,
    formats,
    quality,
  } = albumRelease;

  const { ref, inView } = useInView({
    triggerOnce: true,
    rootMargin: "200px",
  });

  const navigate = useNavigate();
  const artistNames = artists?.map((a) => a.name).join(", ") || "—";
  const formattedDate = release_date ? new Date(release_date).toLocaleDateString() : "—";

  const handlePlay = (e) => {
    e.stopPropagation(); // prevent row click navigation
    console.log("Play album:", album_uuid);
  };

  const handleAddToQueue = (e) => {
    e.stopPropagation();
    console.log("Add album to queue:", album_uuid);
  };

  return (
    <TableRow
      hover
      onClick={() => navigate(`/album/${album_uuid}`)}
      sx={{
        cursor: "pointer",
        position: "relative",
        "&:hover .action-buttons": { opacity: 1 }, // show buttons only on hover
      }}
    >
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
      {/* Hidden action buttons */}
      <TableCell
        align="right"
        sx={{ width: 100, position: "relative" }}
      >
        {formats?.some(
            (f) => f.format === "digital" && f.status === "owned"
          ) && (
            <Box
              className="action-buttons"
              sx={{
                display: "flex",
                gap: 1,
                opacity: 0,
                transition: "opacity 0.2s",
              }}
            >
              <IconButton
                size="small"
                color="primary"
                onClick={(e) => handlePlay(e, albumRelease.album_uuid)}
              >
                <PlayArrowIcon />
              </IconButton>
              <IconButton
                size="small"
                color="primary"
                onClick={(e) => handleAddToQueue(e, albumRelease.album_uuid)}
              >
                <QueueMusicIcon />
              </IconButton>
            </Box>)}
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
