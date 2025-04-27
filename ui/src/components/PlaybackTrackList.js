import React from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Link,
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
              <TableCell>
                {play.track_uuid ? (
                  <Link href={`/track/${play.track_uuid}`} underline="hover">
                    {play.song_title || "Unknown"}
                  </Link>
                ) : (
                  play.song_title || "Unknown"
                )}
              </TableCell>
              <TableCell>
                {play.artists && play.artists.length > 0
                  ? play.artists.map((artist, index) => (
                      <React.Fragment key={artist.artist_uuid}>
                        <Link href={`/artist/${artist.artist_uuid}`} underline="hover">
                          {artist.name}
                        </Link>
                        {index < play.artists.length - 1 ? ", " : ""}
                      </React.Fragment>
                    ))
                  : "Unknown"}
              </TableCell>
              <TableCell>
                {play.album_uuid ? (
                  <Link href={`/album/${play.album_uuid}`} underline="hover">
                    {play.album_title || "Unknown"}
                  </Link>
                ) : (
                  play.album_title || "Unknown"
                )}
              </TableCell>
              <TableCell>
                {new Date(play.played_at).toLocaleString(undefined, {
                  year: "numeric",
                  month: "2-digit",
                  day: "2-digit",
                  hour: "2-digit",
                  minute: "2-digit",
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
