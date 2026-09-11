// Abstract mesh/route graphic used as the overview hero backdrop.
// Nodes = trucks/depots, edges = mesh links or routes.
const nodes = [
  { x: 40, y: 70 }, { x: 130, y: 40 }, { x: 230, y: 90 }, { x: 320, y: 50 },
  { x: 410, y: 100 }, { x: 90, y: 160 }, { x: 200, y: 190 }, { x: 300, y: 160 },
  { x: 390, y: 190 }, { x: 470, y: 130 }, { x: 150, y: 250 }, { x: 260, y: 260 },
  { x: 350, y: 240 },
];

const edges = [
  [0, 1], [1, 2], [2, 3], [3, 4], [1, 5], [2, 6], [3, 7], [4, 8], [4, 9],
  [5, 6], [6, 7], [7, 8], [8, 9], [5, 10], [6, 11], [7, 12], [10, 11], [11, 12],
];

export default function MeshHero() {
  return (
    <svg
      viewBox="0 0 520 300"
      className="w-full h-full"
      preserveAspectRatio="xMidYMid meet"
      aria-hidden="true"
    >
      {edges.map(([a, b], i) => (
        <line
          key={i}
          x1={nodes[a].x}
          y1={nodes[a].y}
          x2={nodes[b].x}
          y2={nodes[b].y}
          stroke="#233042"
          strokeWidth="1"
        />
      ))}
      {/* highlighted recovery path */}
      {[5, 6, 11, 12].map((n, i, arr) =>
        i < arr.length - 1 ? (
          <line
            key={`h-${i}`}
            x1={nodes[n].x}
            y1={nodes[n].y}
            x2={nodes[arr[i + 1]].x}
            y2={nodes[arr[i + 1]].y}
            stroke="#4dd9c4"
            strokeWidth="1.75"
            strokeDasharray="5 4"
          />
        ) : null
      )}
      {nodes.map((n, i) => (
        <circle
          key={i}
          cx={n.x}
          cy={n.y}
          r={i === 9 ? 5 : 3.5}
          fill={i === 9 ? "#f5a623" : "#5b6779"}
        />
      ))}
      {[5, 6, 11, 12].map((n) => (
        <circle key={`hl-${n}`} cx={nodes[n].x} cy={nodes[n].y} r={4} fill="#4dd9c4" />
      ))}
    </svg>
  );
}
