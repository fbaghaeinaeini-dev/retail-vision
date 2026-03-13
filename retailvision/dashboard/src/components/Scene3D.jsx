import { Suspense, useMemo } from "react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls, Grid, Text } from "@react-three/drei";
import { getZoneColor } from "../lib/colors";

/**
 * Three.js 3D scene viewer for zone layout.
 * Renders zone polygons as extruded shapes on a ground plane.
 */
export default function Scene3D({ zones, scene3d }) {
  const zoneList = useMemo(() => {
    return Object.entries(zones || {})
      .filter(([, z]) => z.polygon_bev?.length >= 3)
      .map(([zid, z]) => ({
        id: zid,
        name: z.business_name || zid,
        type: z.zone_type || "unknown",
        polygon: z.polygon_bev,
        centroid: z.centroid_bev || [0, 0],
        depth: z.depth_info?.avg_depth_m || 2,
      }));
  }, [zones]);

  if (!zoneList.length) {
    return (
      <div className="bg-bg-card border border-border rounded-xl p-6 text-center">
        <p className="text-text-secondary text-sm">No 3D data available</p>
      </div>
    );
  }

  // Compute scene bounds for camera
  const allX = zoneList.flatMap((z) => z.polygon.map(([x]) => x));
  const allY = zoneList.flatMap((z) => z.polygon.map(([, y]) => y));
  const cx = (Math.min(...allX) + Math.max(...allX)) / 2;
  const cy = (Math.min(...allY) + Math.max(...allY)) / 2;
  const span = Math.max(Math.max(...allX) - Math.min(...allX), Math.max(...allY) - Math.min(...allY));

  return (
    <div className="bg-bg-card border border-border rounded-xl overflow-hidden">
      <div className="px-4 py-2 border-b border-border">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
          3D Scene View
        </h3>
      </div>
      <div style={{ height: 400 }}>
        <Canvas
          camera={{
            position: [cx, span * 0.8, cy + span * 0.6],
            fov: 50,
            near: 0.1,
            far: span * 10,
          }}
        >
          <ambientLight intensity={0.4} />
          <directionalLight position={[cx, span, cy]} intensity={0.6} />

          <Suspense fallback={null}>
            {/* Ground grid */}
            <Grid
              args={[span * 2, span * 2]}
              position={[cx, 0, cy]}
              cellSize={1}
              cellThickness={0.5}
              cellColor="#1e1e2e"
              sectionSize={5}
              sectionThickness={1}
              sectionColor="#2a2a3e"
              fadeDistance={span * 2}
              infiniteGrid
            />

            {/* Zone blocks */}
            {zoneList.map((z) => (
              <ZoneBlock key={z.id} zone={z} />
            ))}
          </Suspense>

          <OrbitControls
            target={[cx, 0, cy]}
            enableDamping
            dampingFactor={0.1}
            maxPolarAngle={Math.PI / 2.2}
          />
        </Canvas>
      </div>
    </div>
  );
}

function ZoneBlock({ zone }) {
  const color = getZoneColor(zone.type);
  const height = Math.max(zone.depth * 0.3, 0.5);

  // Compute bounding box from polygon for simple box representation
  const xs = zone.polygon.map(([x]) => x);
  const ys = zone.polygon.map(([, y]) => y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const w = maxX - minX;
  const d = maxY - minY;
  const cx = (minX + maxX) / 2;
  const cz = (minY + maxY) / 2;

  return (
    <group position={[cx, height / 2, cz]}>
      <mesh>
        <boxGeometry args={[w, height, d]} />
        <meshStandardMaterial color={color} transparent opacity={0.6} />
      </mesh>
      <mesh>
        <boxGeometry args={[w, height, d]} />
        <meshStandardMaterial color={color} wireframe />
      </mesh>
      <Text
        position={[0, height / 2 + 0.3, 0]}
        rotation={[-Math.PI / 2, 0, 0]}
        fontSize={Math.max(w * 0.1, 0.5)}
        color="white"
        anchorX="center"
        anchorY="middle"
      >
        {zone.name}
      </Text>
    </group>
  );
}
