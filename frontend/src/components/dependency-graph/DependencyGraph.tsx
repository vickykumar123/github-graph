/**
 * DependencyGraph - D3.js Force-Directed Graph Visualization
 *
 * Enhanced with:
 * - Curved edges for better readability
 * - Gradient fills and glow effects
 * - Better spacing for dense graphs
 * - Animated nodes
 */

import {useEffect, useRef, useState} from "react";
import * as d3 from "d3";
import type {GraphNode, GraphEdge} from "@/hooks/query/repository";

// Vibrant language colors with gradients
const LANGUAGE_COLORS: Record<string, {primary: string; secondary: string}> = {
  python: {primary: "#3572A5", secondary: "#6B9BD1"},
  javascript: {primary: "#f1e05a", secondary: "#FFF176"},
  typescript: {primary: "#3178c6", secondary: "#5C9CE6"},
  rust: {primary: "#dea584", secondary: "#F0C4A8"},
  go: {primary: "#00ADD8", secondary: "#4DD0E1"},
  java: {primary: "#b07219", secondary: "#D4994D"},
  c: {primary: "#555555", secondary: "#888888"},
  cpp: {primary: "#f34b7d", secondary: "#FF7FA3"},
  php: {primary: "#4F5D95", secondary: "#7986CB"},
  ruby: {primary: "#701516", secondary: "#A33234"},
  default: {primary: "#8b5cf6", secondary: "#A78BFA"},
};

interface DependencyGraphProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  onNodeClick?: (node: GraphNode) => void;
  selectedNodeId?: string | null;
}

// Extended node type for D3 simulation
interface SimulationNode extends GraphNode {
  x?: number;
  y?: number;
  fx?: number | null;
  fy?: number | null;
  connectionCount?: number;
}

// Extended edge type for D3 simulation
interface SimulationEdge {
  source: SimulationNode | string;
  target: SimulationNode | string;
  type: string;
}

export default function DependencyGraph({
  nodes,
  edges,
  onNodeClick,
  selectedNodeId,
}: DependencyGraphProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({width: 800, height: 600});
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);

  // Update dimensions on resize
  useEffect(() => {
    const updateDimensions = () => {
      if (containerRef.current) {
        const {width, height} = containerRef.current.getBoundingClientRect();
        setDimensions({width, height});
      }
    };

    updateDimensions();
    window.addEventListener("resize", updateDimensions);
    return () => window.removeEventListener("resize", updateDimensions);
  }, []);

  // D3 visualization
  useEffect(() => {
    if (!svgRef.current || nodes.length === 0) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const {width, height} = dimensions;

    // Create defs for gradients and filters
    const defs = svg.append("defs");

    // Create gradients for each language
    Object.entries(LANGUAGE_COLORS).forEach(([lang, colors]) => {
      const gradient = defs.append("radialGradient")
        .attr("id", `gradient-${lang}`)
        .attr("cx", "30%")
        .attr("cy", "30%");

      gradient.append("stop")
        .attr("offset", "0%")
        .attr("stop-color", colors.secondary);

      gradient.append("stop")
        .attr("offset", "100%")
        .attr("stop-color", colors.primary);
    });

    // Glow filter for hover/selected states
    const glowFilter = defs.append("filter")
      .attr("id", "glow")
      .attr("x", "-50%")
      .attr("y", "-50%")
      .attr("width", "200%")
      .attr("height", "200%");

    glowFilter.append("feGaussianBlur")
      .attr("stdDeviation", "4")
      .attr("result", "coloredBlur");

    const glowMerge = glowFilter.append("feMerge");
    glowMerge.append("feMergeNode").attr("in", "coloredBlur");
    glowMerge.append("feMergeNode").attr("in", "SourceGraphic");

    // Drop shadow filter
    const shadowFilter = defs.append("filter")
      .attr("id", "shadow")
      .attr("x", "-50%")
      .attr("y", "-50%")
      .attr("width", "200%")
      .attr("height", "200%");

    shadowFilter.append("feDropShadow")
      .attr("dx", "0")
      .attr("dy", "2")
      .attr("stdDeviation", "3")
      .attr("flood-color", "rgba(0,0,0,0.3)");

    // Arrow marker with gradient
    const marker = defs.append("marker")
      .attr("id", "arrowhead")
      .attr("viewBox", "-0 -5 10 10")
      .attr("refX", 32)
      .attr("refY", 0)
      .attr("orient", "auto")
      .attr("markerWidth", 6)
      .attr("markerHeight", 6);

    marker.append("path")
      .attr("d", "M 0,-4 L 8,0 L 0,4")
      .attr("fill", "#6366f1")
      .attr("opacity", 0.8);

    // Highlighted arrow marker
    const markerHighlight = defs.append("marker")
      .attr("id", "arrowhead-highlight")
      .attr("viewBox", "-0 -5 10 10")
      .attr("refX", 32)
      .attr("refY", 0)
      .attr("orient", "auto")
      .attr("markerWidth", 8)
      .attr("markerHeight", 8);

    markerHighlight.append("path")
      .attr("d", "M 0,-4 L 8,0 L 0,4")
      .attr("fill", "#a855f7");

    // Create container group for zoom/pan
    const g = svg.append("g");

    // Add zoom behavior
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on("zoom", (event) => {
        g.attr("transform", event.transform);
      });

    svg.call(zoom);

    // Count connections per node for better layout
    const connectionCounts = new Map<string, number>();
    edges.forEach((e) => {
      connectionCounts.set(e.source, (connectionCounts.get(e.source) || 0) + 1);
      connectionCounts.set(e.target, (connectionCounts.get(e.target) || 0) + 1);
    });

    // Prepare data for simulation
    const simulationNodes: SimulationNode[] = nodes.map((d) => ({
      ...d,
      connectionCount: connectionCounts.get(d.id) || 0,
    }));
    const simulationEdges: SimulationEdge[] = edges.map((d) => ({...d}));

    // Calculate adaptive forces based on graph density
    const density = edges.length / Math.max(nodes.length, 1);
    const linkDistance = Math.max(150, 200 + density * 30);
    const chargeStrength = Math.min(-80, -150 - density * 20);

    // Create force simulation with improved spacing
    const simulation = d3.forceSimulation(simulationNodes)
      .force("link", d3.forceLink<SimulationNode, SimulationEdge>(simulationEdges)
        .id((d) => d.id)
        .distance(linkDistance)
        .strength(0.8)
      )
      .force("charge", d3.forceManyBody()
        .strength((d) => {
          // Nodes with more connections need more space
          const node = d as SimulationNode;
          return chargeStrength - (node.connectionCount || 0) * 15;
        })
      )
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collision", d3.forceCollide()
        .radius((d) => {
          const node = d as SimulationNode;
          return 45 + (node.connectionCount || 0) * 3;
        })
      )
      .force("x", d3.forceX(width / 2).strength(0.03))
      .force("y", d3.forceY(height / 2).strength(0.03));

    // Draw curved edges
    const link = g.append("g")
      .attr("class", "links")
      .selectAll("path")
      .data(simulationEdges)
      .join("path")
      .attr("fill", "none")
      .attr("stroke", "#6366f1")
      .attr("stroke-opacity", 0.4)
      .attr("stroke-width", 2)
      .attr("marker-end", "url(#arrowhead)");

    // Draw nodes
    const node = g.append("g")
      .attr("class", "nodes")
      .selectAll<SVGGElement, SimulationNode>("g")
      .data(simulationNodes)
      .join("g")
      .attr("cursor", "pointer")
      .call(d3.drag<SVGGElement, SimulationNode>()
        .on("start", (event, d) => {
          if (!event.active) simulation.alphaTarget(0.3).restart();
          d.fx = d.x;
          d.fy = d.y;
        })
        .on("drag", (event, d) => {
          d.fx = event.x;
          d.fy = event.y;
        })
        .on("end", (event, d) => {
          if (!event.active) simulation.alphaTarget(0);
          d.fx = null;
          d.fy = null;
        })
      );

    // Outer glow ring for nodes with external dependencies
    node.filter((d) => d.has_external_dependencies)
      .append("circle")
      .attr("r", 24)
      .attr("fill", "none")
      .attr("stroke", "#fbbf24")
      .attr("stroke-width", 2)
      .attr("stroke-dasharray", "4 2")
      .attr("opacity", 0.6)
      .attr("class", "pulse-ring");

    // Node circles with gradients
    node.append("circle")
      .attr("r", (d) => d.has_external_dependencies ? 18 : 14)
      .attr("fill", (d) => {
        const lang = d.language?.toLowerCase() || "default";
        return `url(#gradient-${LANGUAGE_COLORS[lang] ? lang : "default"})`;
      })
      .attr("stroke", (d) => d.id === selectedNodeId ? "#fff" : "rgba(255,255,255,0.2)")
      .attr("stroke-width", (d) => d.id === selectedNodeId ? 3 : 1)
      .attr("filter", "url(#shadow)")
      .attr("class", "node-circle");

    // Inner highlight for 3D effect
    node.append("circle")
      .attr("r", (d) => (d.has_external_dependencies ? 18 : 14) * 0.4)
      .attr("cx", -3)
      .attr("cy", -3)
      .attr("fill", "rgba(255,255,255,0.3)")
      .attr("pointer-events", "none");

    // Node labels with background
    const labelGroup = node.append("g")
      .attr("transform", "translate(22, 0)");

    // Label background
    labelGroup.append("rect")
      .attr("x", -4)
      .attr("y", -10)
      .attr("rx", 4)
      .attr("ry", 4)
      .attr("fill", "rgba(17, 24, 39, 0.8)")
      .attr("class", "label-bg");

    // Label text
    const labelText = labelGroup.append("text")
      .text((d) => d.filename)
      .attr("y", 4)
      .attr("font-size", "11px")
      .attr("font-weight", "500")
      .attr("fill", "#e5e7eb")
      .attr("pointer-events", "none");

    // Size label backgrounds to fit text
    labelGroup.each(function() {
      const textNode = d3.select(this).select("text").node() as SVGTextElement;
      const bbox = textNode.getBBox();
      d3.select(this).select("rect")
        .attr("width", bbox.width + 8)
        .attr("height", bbox.height + 6);
    });

    // Node interactions
    node
      .on("click", (event, d) => {
        event.stopPropagation();
        onNodeClick?.(d);
      })
      .on("mouseenter", (event, d) => {
        setHoveredNode(d.id);

        // Scale up hovered node
        d3.select(event.currentTarget)
          .select(".node-circle")
          .transition()
          .duration(200)
          .attr("r", d.has_external_dependencies ? 22 : 18)
          .attr("filter", "url(#glow)");

        // Highlight connected edges with curves
        link
          .transition()
          .duration(200)
          .attr("stroke-opacity", (l) => {
            const source = typeof l.source === "object" ? l.source.id : l.source;
            const target = typeof l.target === "object" ? l.target.id : l.target;
            return source === d.id || target === d.id ? 0.9 : 0.1;
          })
          .attr("stroke", (l) => {
            const source = typeof l.source === "object" ? l.source.id : l.source;
            const target = typeof l.target === "object" ? l.target.id : l.target;
            return source === d.id || target === d.id ? "#a855f7" : "#6366f1";
          })
          .attr("stroke-width", (l) => {
            const source = typeof l.source === "object" ? l.source.id : l.source;
            const target = typeof l.target === "object" ? l.target.id : l.target;
            return source === d.id || target === d.id ? 3 : 2;
          })
          .attr("marker-end", (l) => {
            const source = typeof l.source === "object" ? l.source.id : l.source;
            const target = typeof l.target === "object" ? l.target.id : l.target;
            return source === d.id || target === d.id ? "url(#arrowhead-highlight)" : "url(#arrowhead)";
          });

        // Dim non-connected nodes
        node.transition()
          .duration(200)
          .attr("opacity", (n) => {
            if (n.id === d.id) return 1;
            const isConnected = simulationEdges.some((e) => {
              const source = typeof e.source === "object" ? e.source.id : e.source;
              const target = typeof e.target === "object" ? e.target.id : e.target;
              return (source === d.id && target === n.id) || (target === d.id && source === n.id);
            });
            return isConnected ? 1 : 0.3;
          });
      })
      .on("mouseleave", (event, d) => {
        setHoveredNode(null);

        // Reset node size
        d3.select(event.currentTarget)
          .select(".node-circle")
          .transition()
          .duration(200)
          .attr("r", d.has_external_dependencies ? 18 : 14)
          .attr("filter", "url(#shadow)");

        // Reset edges
        link
          .transition()
          .duration(200)
          .attr("stroke-opacity", 0.4)
          .attr("stroke", "#6366f1")
          .attr("stroke-width", 2)
          .attr("marker-end", "url(#arrowhead)");

        // Reset node opacity
        node.transition()
          .duration(200)
          .attr("opacity", 1);
      });

    // Curved path generator
    const linkArc = (d: SimulationEdge) => {
      const source = d.source as SimulationNode;
      const target = d.target as SimulationNode;
      const dx = target.x! - source.x!;
      const dy = target.y! - source.y!;
      const dr = Math.sqrt(dx * dx + dy * dy) * 0.8; // Curve radius
      return `M${source.x},${source.y}A${dr},${dr} 0 0,1 ${target.x},${target.y}`;
    };

    // Update positions on simulation tick
    simulation.on("tick", () => {
      link.attr("d", linkArc);
      node.attr("transform", (d) => `translate(${d.x},${d.y})`);
    });

    // Initial zoom to fit
    const initialScale = Math.min(
      width / 1200,
      height / 900,
      0.9
    );
    svg.call(zoom.transform, d3.zoomIdentity
      .translate(width / 2, height / 2)
      .scale(initialScale)
      .translate(-width / 2, -height / 2)
    );

    return () => {
      simulation.stop();
    };
  }, [nodes, edges, dimensions, selectedNodeId, onNodeClick]);

  // Find hovered node data for tooltip
  const hoveredNodeData = hoveredNode ? nodes.find((n) => n.id === hoveredNode) : null;

  return (
    <div ref={containerRef} className="relative w-full h-full bg-gradient-to-br from-[#0f0f1a] to-[#1a1a2e]">
      {/* Decorative background pattern */}
      <div className="absolute inset-0 opacity-5 pointer-events-none">
        <svg width="100%" height="100%">
          <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
            <path d="M 40 0 L 0 0 0 40" fill="none" stroke="white" strokeWidth="0.5" />
          </pattern>
          <rect width="100%" height="100%" fill="url(#grid)" />
        </svg>
      </div>

      <svg
        ref={svgRef}
        width={dimensions.width}
        height={dimensions.height}
        className="w-full h-full"
      />

      {/* Animated pulse style */}
      <style>{`
        @keyframes pulse-ring {
          0% { opacity: 0.6; transform: scale(1); }
          50% { opacity: 0.3; transform: scale(1.1); }
          100% { opacity: 0.6; transform: scale(1); }
        }
        .pulse-ring {
          animation: pulse-ring 2s ease-in-out infinite;
          transform-origin: center;
          transform-box: fill-box;
        }
      `}</style>

      {/* Enhanced Tooltip */}
      {hoveredNodeData && (
        <div className="absolute top-4 left-4 bg-gradient-to-br from-[#1e1e2e] to-[#2a2a3e] border border-purple-500/30 rounded-xl p-4 shadow-2xl max-w-xs backdrop-blur-sm">
          <div className="flex items-start gap-3">
            <div
              className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0"
              style={{
                background: `linear-gradient(135deg, ${
                  LANGUAGE_COLORS[hoveredNodeData.language?.toLowerCase() || "default"]?.secondary
                }, ${
                  LANGUAGE_COLORS[hoveredNodeData.language?.toLowerCase() || "default"]?.primary
                })`,
              }}
            >
              <span className="text-white text-xs font-bold">
                {hoveredNodeData.language?.slice(0, 2).toUpperCase() || "?"}
              </span>
            </div>
            <div className="min-w-0">
              <p className="font-mono text-sm font-semibold text-white truncate">{hoveredNodeData.filename}</p>
              <p className="text-xs text-gray-400 truncate">{hoveredNodeData.path}</p>
            </div>
          </div>

          <div className="flex flex-wrap gap-2 mt-3">
            <span className="px-2 py-1 rounded-full bg-purple-500/20 text-purple-300 text-xs font-medium capitalize">
              {hoveredNodeData.language}
            </span>
            {hoveredNodeData.functions.length > 0 && (
              <span className="px-2 py-1 rounded-full bg-blue-500/20 text-blue-300 text-xs">
                {hoveredNodeData.functions.length} functions
              </span>
            )}
            {hoveredNodeData.classes.length > 0 && (
              <span className="px-2 py-1 rounded-full bg-green-500/20 text-green-300 text-xs">
                {hoveredNodeData.classes.length} classes
              </span>
            )}
          </div>

          {hoveredNodeData.has_external_dependencies && (
            <div className="flex items-center gap-2 mt-3 px-2 py-1.5 rounded-lg bg-yellow-500/10 border border-yellow-500/20">
              <svg className="w-4 h-4 text-yellow-400" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
              </svg>
              <span className="text-xs text-yellow-300">Has external dependencies</span>
            </div>
          )}
        </div>
      )}

      {/* Enhanced Legend */}
      <div className="absolute bottom-4 right-4 bg-gradient-to-br from-[#1e1e2e] to-[#2a2a3e] border border-purple-500/20 rounded-xl p-4 backdrop-blur-sm">
        <p className="text-xs font-semibold mb-3 text-purple-300 uppercase tracking-wider">Languages</p>
        <div className="grid grid-cols-2 gap-x-6 gap-y-2">
          {Object.entries(LANGUAGE_COLORS).slice(0, 8).filter(([lang]) => lang !== "default").map(([lang, colors]) => (
            <div key={lang} className="flex items-center gap-2">
              <div
                className="w-3 h-3 rounded-full shadow-lg"
                style={{background: `linear-gradient(135deg, ${colors.secondary}, ${colors.primary})`}}
              />
              <span className="text-xs text-gray-300 capitalize">{lang}</span>
            </div>
          ))}
        </div>
        <div className="mt-3 pt-3 border-t border-purple-500/20">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full border-2 border-dashed border-yellow-400" />
            <span className="text-xs text-gray-400">External deps</span>
          </div>
        </div>
      </div>

      {/* Controls hint */}
      <div className="absolute bottom-4 left-4 px-3 py-2 rounded-lg bg-[#1e1e2e]/80 border border-purple-500/10 backdrop-blur-sm">
        <p className="text-xs text-gray-400">
          <span className="text-purple-400">Scroll</span> to zoom • <span className="text-purple-400">Drag</span> to pan • <span className="text-purple-400">Click</span> node to view
        </p>
      </div>
    </div>
  );
}
