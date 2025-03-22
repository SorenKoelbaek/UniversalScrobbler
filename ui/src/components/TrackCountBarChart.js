// src/components/TrackCountBarChart.js
import React, { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import apiClient from "../utils/apiClient";
import { Paper, Typography } from "@mui/material";
import dayjs from "dayjs";

const TrackCountBarChart = () => {
  const [data, setData] = useState([]);

  useEffect(() => {
    apiClient.get("/consumption/history?days=7").then((response) => {
      const counts = {};

      response.data.forEach((entry) => {
        const day = dayjs(entry.played_at).format("ddd"); // e.g. "Mon"
        counts[day] = (counts[day] || 0) + 1;
      });

      const chartData = Object.entries(counts).map(([day, count]) => ({
        day,
        count,
      }));

      setData(chartData);
    });
  }, []);

  return (
    <Paper sx={{ padding: 2, height: "100%" }}>
      <Typography variant="subtitle1" gutterBottom>
        Tracks Played (Last 7 Days)
      </Typography>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="day" />
          <YAxis allowDecimals={false} />
          <Tooltip />
          <Bar dataKey="count" fill="#4caf50" />
        </BarChart>
      </ResponsiveContainer>
    </Paper>
  );
};

export default TrackCountBarChart;
