// components/PlaybackQueueList.jsx
import React from "react";
import {
  List,
  ListItem,
  ListItemText,
  Divider,
  IconButton,
  Box,
} from "@mui/material";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import DragHandleIcon from "@mui/icons-material/DragHandle";

import {
  DndContext,
  closestCenter,
  PointerSensor,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
  arrayMove,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";

function SortableItem({ item, isCurrent, onPlayTrack }) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
  } = useSortable({ id: item.playback_queue_uuid });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    backgroundColor: isCurrent ? "rgba(25, 118, 210, 0.2)" : "transparent",
  };

  return (
    <React.Fragment>
      <ListItem ref={setNodeRef} style={style}>
        <ListItemText
          primary={item.track.name}
          secondary={item.track.artists?.map((a) => a.name).join(", ")}
        />
        <Box sx={{ display: "flex", gap: 1 }}>
          {/* Drag handle */}
          <IconButton edge="end" size="small" {...attributes} {...listeners}>
            <DragHandleIcon />
          </IconButton>
          {/* Play this track */}
          <IconButton edge="end" size="small" onClick={() => onPlayTrack(item)}>
            <PlayArrowIcon />
          </IconButton>
        </Box>
      </ListItem>
      <Divider />
    </React.Fragment>
  );
}

/**
 * PlaybackQueueList
 *
 * Props:
 * - queue: Array of queue items (PlaybackQueueItem)
 * - currentTrack: current track object { track_uuid, ... }
 * - onPlayTrack: (item) => void
 * - onReorder: (newOrder: string[]) => void
 */
const PlaybackQueueList = ({ queue, currentTrack, onPlayTrack, onReorder }) => {
  const sensors = useSensors(useSensor(PointerSensor));

  const handleDragEnd = (event) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;

    const oldIndex = queue.findIndex((i) => i.playback_queue_uuid === active.id);
    const newIndex = queue.findIndex((i) => i.playback_queue_uuid === over.id);

    const reordered = arrayMove(queue, oldIndex, newIndex);
    onReorder(reordered.map((item) => item.playback_queue_uuid));
  };

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragEnd={handleDragEnd}
    >
      <SortableContext
        items={queue.map((i) => i.playback_queue_uuid)}
        strategy={verticalListSortingStrategy}
      >
        <List dense>
          {queue.map((item) => (
            <SortableItem
              key={item.playback_queue_uuid}
              item={item}
              isCurrent={currentTrack && item.track.track_uuid === currentTrack.track_uuid}
              onPlayTrack={onPlayTrack}
            />
          ))}
        </List>
      </SortableContext>
    </DndContext>
  );
};

export default PlaybackQueueList;
