import { Environment, Lightformer } from '@react-three/drei';

export function StudioLights() {
  return (
    <>
      <ambientLight intensity={0.4} color="#EDE7DC" />
      <directionalLight position={[3, 5, 4]} intensity={1.5} color="#EDE7DC" />
      <directionalLight position={[-4, 2, -3]} intensity={0.8} color="#9EA5A8" />
      <directionalLight position={[0, -3, 2]} intensity={0.3} color="#2E6B72" />
      <Environment resolution={256} frames={1}>
        {/* Key light in warm bone */}
        <Lightformer
          form="rect"
          intensity={2.5}
          color="#EDE7DC"
          scale={[10, 3, 1]}
          position={[0, 5, -6]}
          target={[0, 0, 0]}
        />
        {/* Fill light in neutral secondary ink */}
        <Lightformer
          form="rect"
          intensity={1.0}
          color="#9EA5A8"
          scale={[4, 8, 1]}
          position={[-6, 0, 2]}
        />
        {/* Subtle rim light */}
        <Lightformer
          form="rect"
          intensity={1.5}
          color="#EDE7DC"
          scale={[3, 8, 1]}
          position={[6, 1, 1]}
        />
      </Environment>
    </>
  );
}
