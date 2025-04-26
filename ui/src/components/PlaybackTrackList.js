import React from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
} from "@mui/material";

const PlaybackTrackList = ({ plays }) => {
  return (
    <TableContainer component={Paper}>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Track</TableCell>
            <TableCell>Artist</TableCell>
            <TableCell>Album</TableCell>
            <TableCell>Played At</TableCell>
            <TableCell>Source</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {plays.map((play) => (
            <TableRow key={play.playback_history_uuid}>
              <TableCell>{play.song_title || "Unknown"}</TableCell>
              <TableCell>{play.artists?.map(a => a.name).join(", ") || "Unknown"}</TableCell>
              <TableCell>{play.album_title || "Unknown"}</TableCell>
              <TableCell>
                {new Date(play.played_at).toLocaleString(undefined, {
                  year: 'numeric',
                  month: '2-digit',
                  day: '2-digit',
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </TableCell>
              <TableCell>{play.source}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
};

export default PlaybackTrackList;
