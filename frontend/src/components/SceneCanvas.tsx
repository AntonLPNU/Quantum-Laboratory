import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { Html, Line, OrbitControls, Stars } from '@react-three/drei';
import { useEffect, useMemo, useRef } from 'react';
import * as THREE from 'three';
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib';
import type { Spin } from '../data/mockData';

type SceneProps = Readonly<{
  selectedSpin: string;
  onSelectSpin: (id: string) => void;
  spins: readonly Spin[];
  entangledPair: readonly [number, number];
  interactionOn: boolean;
  tool: 'orbit' | 'pan' | 'zoom';
  cameraMode: 'orbit' | 'fly';
  hideCaption?: boolean;
  onControlsReady: (controls: OrbitControlsImpl | null) => void;
  onFps: (fps: number) => void;
}>;

/** Clickable schematic node; its position represents layout only, not particle motion. */
function SpinNode({ id, label, position, selected, onSelect }: {
  id: string; label: string; position: readonly [number, number, number]; selected: boolean; onSelect: (id: string) => void;
}) {
  return <group position={position}>
    <mesh onClick={event => { event.stopPropagation(); onSelect(id); }}>
      <sphereGeometry args={[selected ? 0.36 : 0.29, 32, 32]} />
      <meshStandardMaterial color={selected ? '#62D8E8' : '#263547'} emissive={selected ? '#1E7681' : '#0C1825'} emissiveIntensity={selected ? 0.7 : 0.4} metalness={0.35} roughness={0.28} />
    </mesh>
    <mesh>
      <sphereGeometry args={[selected ? 0.48 : 0.39, 14, 10]} />
      <meshBasicMaterial color={selected ? '#62D8E8' : '#53677D'} wireframe transparent opacity={selected ? 0.42 : 0.25} />
    </mesh>
    <Html center distanceFactor={10} position={[0, -0.66, 0]} style={{ pointerEvents: 'none' }}>
      <span className={`spin-label${selected ? ' is-selected' : ''}`}>{label} <small>{id}</small></span>
    </Html>
  </group>;
}

/** Optional first-person camera controls; this changes only the view, never the simulation state. */
function FlyCamera({ enabled }: { enabled: boolean }) {
  const { camera, gl } = useThree();
  const movement = useRef({ forward: false, back: false, left: false, right: false, up: false, down: false });
  useEffect(() => {
    if (!enabled) return;
    const canvas = gl.domElement;
    const click = () => canvas.requestPointerLock?.();
    const down = (event: KeyboardEvent) => { const key = event.key.toLowerCase(); if (key === 'w') movement.current.forward = true; if (key === 's') movement.current.back = true; if (key === 'a') movement.current.left = true; if (key === 'd') movement.current.right = true; if (key === 'q') movement.current.down = true; if (key === 'e') movement.current.up = true; };
    const up = (event: KeyboardEvent) => { const key = event.key.toLowerCase(); if (key === 'w') movement.current.forward = false; if (key === 's') movement.current.back = false; if (key === 'a') movement.current.left = false; if (key === 'd') movement.current.right = false; if (key === 'q') movement.current.down = false; if (key === 'e') movement.current.up = false; };
    const look = (event: MouseEvent) => { if (document.pointerLockElement !== canvas) return; camera.rotation.order = 'YXZ'; camera.rotation.y -= event.movementX * 0.002; camera.rotation.x = THREE.MathUtils.clamp(camera.rotation.x - event.movementY * 0.002, -1.45, 1.45); };
    canvas.addEventListener('click', click); window.addEventListener('keydown', down); window.addEventListener('keyup', up); window.addEventListener('mousemove', look);
    return () => { canvas.removeEventListener('click', click); window.removeEventListener('keydown', down); window.removeEventListener('keyup', up); window.removeEventListener('mousemove', look); if (document.pointerLockElement === canvas) document.exitPointerLock(); };
  }, [camera, enabled, gl]);
  useFrame((_, delta) => {
    if (!enabled) return;
    const move = movement.current; const speed = delta * 4;
    if (move.forward) camera.translateZ(-speed); if (move.back) camera.translateZ(speed);
    if (move.left) camera.translateX(-speed); if (move.right) camera.translateX(speed);
    if (move.up) camera.translateY(speed); if (move.down) camera.translateY(-speed);
  });
  return null;
}

/** Reports a rolling one-second render-rate estimate for the viewport status display. */
function FpsProbe({ onFps }: { onFps: (fps: number) => void }) {
  const sample = useRef({ frames: 0, seconds: 0 });
  useFrame((_, delta) => {
    if (delta <= 0 || delta > 0.25) return;
    sample.current.frames += 1;
    sample.current.seconds += delta;
    if (sample.current.seconds >= 1) {
      onFps(Math.round(sample.current.frames / sample.current.seconds));
      sample.current = { frames: 0, seconds: 0 };
    }
  });
  return null;
}

/** Draws the Python-provided Bloch vector as a schematic Three.js arrow. */
function BlochArrow({ spin }: { spin: Spin }) {
  const arrow = useMemo(() => {
    const vector = new THREE.Vector3(...spin.bloch);
    const length = vector.length();
    if (length < 1e-8) return null;
    return new THREE.ArrowHelper(vector.normalize(), new THREE.Vector3(0, 0.42, 0), Math.min(0.75, length * 0.62), '#62D8E8', 0.16, 0.09);
  }, [spin.bloch]);
  return arrow ? <primitive object={arrow} dispose={null} /> : null;
}

/** Composes scene geometry and camera controls from the latest UI/API state. */
function QuantumScene({ selectedSpin, onSelectSpin, spins, entangledPair, interactionOn, tool, cameraMode, hideCaption, onControlsReady, onFps }: SceneProps) {
  const controls = useRef<OrbitControlsImpl>(null);
  const mouseButtons = useMemo(() => ({ LEFT: tool === 'orbit' ? THREE.MOUSE.ROTATE : tool === 'pan' ? THREE.MOUSE.PAN : THREE.MOUSE.DOLLY, MIDDLE: THREE.MOUSE.DOLLY, RIGHT: THREE.MOUSE.PAN }), [tool]);
  useEffect(() => { onControlsReady(controls.current); return () => onControlsReady(null); }, [onControlsReady]);
  return <>
    <color attach="background" args={['#0B1018']} />
    <ambientLight intensity={0.7} /><pointLight position={[1, 4, 5]} intensity={22} color="#9BEFFF" /><pointLight position={[-4, -1, -3]} intensity={9} color="#A99BF8" />
    <Stars radius={45} depth={18} count={900} factor={1.3} saturation={0.25} fade speed={0.2} />
    <gridHelper args={[20, 20, '#253648', '#172536']} position={[0, -1.4, 0]} />
    {interactionOn && spins.slice(0, -1).map((spin, index) => <Line key={`link-${spin.id}`} points={[spin.position, spins[index + 1].position]} color="#5C7188" lineWidth={1} transparent opacity={0.5} />)}
    {spins.length > Math.max(...entangledPair) && <Line points={[spins[entangledPair[0]].position, spins[entangledPair[1]].position]} color="#A99BF8" lineWidth={1} dashed dashScale={2} dashSize={0.13} gapSize={0.11} transparent opacity={0.85} />}
    {spins.map(spin => <group key={spin.id}><SpinNode id={spin.id} label={spin.label} position={spin.position} selected={spin.id === selectedSpin} onSelect={onSelectSpin} /><BlochArrow spin={spin} /></group>)}
    {!hideCaption && <Html position={[-5.6, 3.2, 0]}><div className="scene-caption"><span className="eyebrow">СХЕМАТИЧНЕ РОЗТАШУВАННЯ</span><strong>A ⊗ R</strong><span>Стрілка/сфера: математичний вектор Блоха</span><span>Суцільні зв’язки: ненульові сусідні J</span><span>Фіолетовий пунктир: підготовлена Беллова пара</span></div></Html>}
    <OrbitControls ref={controls} makeDefault enabled={cameraMode === 'orbit'} enableDamping dampingFactor={0.08} minDistance={3.5} maxDistance={18} mouseButtons={mouseButtons} />
    <FlyCamera enabled={cameraMode === 'fly'} />
    <FpsProbe onFps={onFps} />
  </>;
}

/** Displays the schematic spin arrangement; all physical values arrive through API-backed props. */
export function SceneCanvas(props: SceneProps) {
  return <Canvas camera={{ position: [0, 1.4, 9.4], fov: 46 }} dpr={[1, 1.6]} gl={{ antialias: true, powerPreference: 'high-performance' }}>
    <QuantumScene {...props} />
  </Canvas>;
}
