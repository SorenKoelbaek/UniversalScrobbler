import React, { useRef, useEffect } from "react";
import * as d3 from "d3";

const TagBubbleChart = ({ tags, width = 500, height = 300, limit = 15 }) => {
  const svgRef = useRef();

  useEffect(() => {
    if (!tags || tags.length === 0) return;

    const filteredTags = tags
      .filter(tag => tag.count > 1)
      .sort((a, b) => b.count - a.count)
      .slice(0, limit);

    const root = d3
      .hierarchy({ children: filteredTags })
      .sum(d => d.count);

    const diameter = Math.min(width, height);
    const pack = d3.pack().size([diameter, diameter]).padding(4);
    const nodes = pack(root).leaves();

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const g = svg
      .attr("viewBox", `0 0 ${width} ${height}`)
      .append("g")
      // 👇 Center the bubble group in the available area
      .attr("transform", `translate(${(width - diameter) / 2}, ${(height - diameter) / 2})`);

    const color = d3.scaleOrdinal()
      .domain(d3.range(limit))
      .range(d3.range(limit).map(i => `hsl(${(i * 360) / limit}, 60%, 50%)`));

    const node = g.selectAll("g")
      .data(nodes)
      .join("g")
      .attr("transform", d => `translate(${d.x},${d.y})`);

    node.append("circle")
      .attr("r", d => d.r)
      .attr("fill", (_, i) => color(i));

    node.append("text")
      .text(d => d.data.name)
      .attr("text-anchor", "middle")
      .attr("dy", ".35em")
      .style("fill", "#fff")
      .style("font-size", d => Math.min(d.r / 2.5, 14))
      .style("pointer-events", "none");

  }, [tags, width, height, limit]);

  return <svg ref={svgRef} width={width} height={height} />;
};

export default TagBubbleChart;
