// Labeled mesh-network diagram, styled like a plain technical figure
// rather than a decorative hero graphic.
const nodes = [
  { id: "T1", x: 60, y: 60 }, { id: "T2", x: 170, y: 35 }, { id: "T3", x: 290, y: 70 },
  { id: "T4", x: 400, y: 45 }, { id: "T5", x: 130, y: 140 }, { id: "T6", x: 250, y: 160 },
  { id: "T7", x: 360, y: 145 }, { id: "DEPOT", x: 210, y: 100 },
];

const idleLinks = [
  [0, 1], [1, 2], [2, 3], [1, 4], [2, 5], [3, 6], [4, 5], [5, 6], [0, 4], [7, 1], [7, 5],
];

const recoveryPath = [4, 5, 6];

export default function MeshFigure() {
  return (
    <svg
      viewBox="0 0 460 200"
      className="w-full h-full"
      role="img"
      aria-label="Mesh network topology diagram showing idle links and a highlighted recovery path"
    >
      {idleLinks.map(([a, b], i) => (
        <line
          key={i}
          x1={nodes[a].x} y1={nodes[a].y}
          x2={nodes[b].x} y2={nodes[b].y}
          stroke="#c9c9bc"
          strokeWidth="1"
        />
      ))}
      {recoveryPath.map((n, i) =>
        i < recoveryPath.length - 1 ? (
          <line
            key={`r-${i}`}
            x1={nodes[n].x} y1={nodes[n].y}
            x2={nodes[recoveryPath[i + 1]].x} y2={nodes[recoveryPath[i + 1]].y}
            stroke="#2e6b34"
            strokeWidth="2"
            strokeDasharray="6 4"
          />
        ) : null
      )}
      {nodes.map((n, i) => {
        const isDepot = n.id === "DEPOT";
        const inRecovery = recoveryPath.includes(i);
        return (
          <g key={n.id}>
            {isDepot ? (
              <rect x={n.x - 5} y={n.y - 5} width={10} height={10} fill="#a13a2e" />
            ) : (
              <circle
                cx={n.x} cy={n.y} r={4}
                fill={inRecovery ? "#2e6b34" : "#61635a"}
              />
            )}
            <text
              x={n.x} y={n.y - 10}
              textAnchor="middle"
              className="mono"
              fontSize="9"
              fill="#61635a"
            >
              {n.id}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
