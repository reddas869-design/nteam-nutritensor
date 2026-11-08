import { useEffect, useRef, useState } from "react";
import * as THREE from "three";

function seedRandom(seed: number) {
  let current = seed;
  return () => {
    current = (current * 16807) % 2147483647;
    return (current - 1) / 2147483646;
  };
}

function createMeal(): THREE.Group {
  const group = new THREE.Group();
  const random = seedRandom(42);
  const ceramic = new THREE.MeshStandardMaterial({
    color: "#ede9dd",
    roughness: 0.76,
    metalness: 0,
  });
  const points: THREE.Vector2[] = [];
  for (let i = 0; i <= 28; i++) {
    const t = i / 28;
    points.push(new THREE.Vector2(0.3 + t * 2.15, 0.08 + t * t * 0.65));
  }
  const bowl = new THREE.Mesh(new THREE.LatheGeometry(points, 100), ceramic);
  bowl.receiveShadow = true;
  bowl.castShadow = true;
  group.add(bowl);
  const rim = new THREE.Mesh(
    new THREE.TorusGeometry(2.45, 0.07, 14, 100),
    ceramic,
  );
  rim.rotation.x = Math.PI / 2;
  rim.position.y = 0.73;
  rim.castShadow = true;
  group.add(rim);
  const base = new THREE.Mesh(
    new THREE.CylinderGeometry(2.07, 1.6, 0.3, 64),
    ceramic,
  );
  base.position.y = 0.23;
  base.receiveShadow = true;
  group.add(base);

  const riceMaterial = new THREE.MeshStandardMaterial({
    color: "#e0d5b5",
    roughness: 0.9,
  });
  const riceGeometry = new THREE.SphereGeometry(0.062, 7, 5);
  riceGeometry.scale(1, 0.65, 2.2);
  const rice = new THREE.InstancedMesh(riceGeometry, riceMaterial, 440);
  const transform = new THREE.Object3D();
  for (let index = 0; index < 440; index++) {
    const angle = random() * Math.PI * 2;
    const radius = Math.sqrt(random()) * 1.28;
    transform.position.set(
      -0.55 + Math.cos(angle) * radius,
      0.45 + random() * 0.25,
      0.25 + Math.sin(angle) * radius,
    );
    transform.rotation.set(random(), random() * Math.PI, random() * 0.7);
    transform.scale.setScalar(0.85 + random() * 0.35);
    transform.updateMatrix();
    rice.setMatrixAt(index, transform.matrix);
  }
  rice.castShadow = true;
  rice.receiveShadow = true;
  group.add(rice);

  const leafMaterials = ["#4f7338", "#638b41", "#7e9b4f", "#355c32"].map(
    (color) =>
      new THREE.MeshStandardMaterial({
        color,
        roughness: 0.85,
        side: THREE.DoubleSide,
      }),
  );
  const leafShape = new THREE.Shape();
  leafShape.moveTo(0, 0);
  leafShape.bezierCurveTo(0.45, 0.05, 0.54, 0.5, 0, 0.9);
  leafShape.bezierCurveTo(-0.42, 0.55, -0.4, 0.16, 0, 0);
  const leafGeometry = new THREE.ShapeGeometry(leafShape, 10);
  for (let index = 0; index < 32; index++) {
    const angle = random() * Math.PI * 2;
    const radius = 1.3 + random() * 0.6;
    const leaf = new THREE.Mesh(
      leafGeometry,
      leafMaterials[index % leafMaterials.length],
    );
    leaf.rotation.set(-Math.PI / 2 + random() * 0.7, random() * 0.2, angle);
    leaf.position.set(
      Math.cos(angle) * radius,
      0.62 + random() * 0.2,
      Math.sin(angle) * radius,
    );
    leaf.scale.setScalar(0.6 + random() * 0.4);
    leaf.castShadow = true;
    group.add(leaf);
  }

  const chickenMaterial = new THREE.MeshStandardMaterial({
    color: "#c5995e",
    roughness: 0.86,
  });
  const chickenInner = new THREE.MeshStandardMaterial({
    color: "#e5c9a2",
    roughness: 0.9,
  });
  const stripeMaterial = new THREE.MeshStandardMaterial({
    color: "#785333",
    roughness: 0.92,
  });
  for (let index = 0; index < 6; index++) {
    const slice = new THREE.Group();
    const meat = new THREE.Mesh(
      new THREE.BoxGeometry(0.3, 0.23, 1.5 - Math.abs(index - 2.5) * 0.15),
      chickenMaterial,
    );
    const face = new THREE.Mesh(
      new THREE.BoxGeometry(0.302, 0.13, 1.37 - Math.abs(index - 2.5) * 0.15),
      chickenInner,
    );
    face.position.y = -0.012;
    slice.add(meat, face);
    for (let stripe = 0; stripe < 3; stripe++) {
      const mark = new THREE.Mesh(
        new THREE.BoxGeometry(0.31, 0.015, 0.035),
        stripeMaterial,
      );
      mark.position.set(0, 0.12, -0.4 + stripe * 0.4);
      mark.rotation.y = 0.12;
      slice.add(mark);
    }
    slice.position.set(-0.68 + index * 0.33, 0.91, -0.45);
    slice.rotation.y = -0.48;
    slice.rotation.z = -0.08;
    meat.castShadow = true;
    face.castShadow = true;
    group.add(slice);
  }

  const tomatoSkin = new THREE.MeshStandardMaterial({
    color: "#b65335",
    roughness: 0.5,
  });
  const tomatoFace = new THREE.MeshStandardMaterial({
    color: "#dd7a4a",
    roughness: 0.8,
  });
  const seedMaterial = new THREE.MeshStandardMaterial({
    color: "#e4b66f",
    roughness: 0.65,
  });
  for (let index = 0; index < 5; index++) {
    const tomato = new THREE.Group();
    const body = new THREE.Mesh(
      new THREE.SphereGeometry(0.24, 20, 12, 0, Math.PI * 2, 0, Math.PI / 2),
      tomatoSkin,
    );
    const face = new THREE.Mesh(
      new THREE.CircleGeometry(0.235, 24),
      tomatoFace,
    );
    face.rotation.x = -Math.PI / 2;
    body.rotation.z = Math.PI;
    face.position.y = 0.015;
    tomato.add(body, face);
    for (let seed = 0; seed < 6; seed++) {
      const dot = new THREE.Mesh(
        new THREE.SphereGeometry(0.021, 5, 4),
        seedMaterial,
      );
      const angle = (seed / 6) * Math.PI * 2;
      dot.position.set(Math.cos(angle) * 0.12, 0.022, Math.sin(angle) * 0.12);
      tomato.add(dot);
    }
    tomato.position.set(1.15 + random() * 0.4, 0.8, -0.6 + index * 0.29);
    tomato.rotation.z = random() * 0.3;
    group.add(tomato);
  }

  const cucumberSkin = new THREE.MeshStandardMaterial({
    color: "#3e6741",
    roughness: 0.8,
  });
  const cucumberInside = new THREE.MeshStandardMaterial({
    color: "#b4c98b",
    roughness: 0.9,
  });
  for (let index = 0; index < 6; index++) {
    const slice = new THREE.Group();
    slice.add(
      new THREE.Mesh(
        new THREE.CylinderGeometry(0.29, 0.29, 0.09, 28),
        cucumberSkin,
      ),
    );
    const inside = new THREE.Mesh(
      new THREE.CylinderGeometry(0.255, 0.255, 0.095, 28),
      cucumberInside,
    );
    slice.add(inside);
    slice.position.set(
      0.15 + index * 0.22,
      0.72 + index * 0.015,
      1.25 - index * 0.07,
    );
    slice.rotation.z = -0.2;
    group.add(slice);
  }
  group.rotation.y = -0.2;
  return group;
}

export default function ThreeScene({
  reducedMotion = false,
}: {
  reducedMotion?: boolean;
}) {
  const container = useRef<HTMLDivElement>(null);
  const [fallback, setFallback] = useState(false);
  useEffect(() => {
    const host = container.current;
    if (!host) return;
    const motionPreference = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    );
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({
        antialias: true,
        alpha: true,
        powerPreference: "low-power",
      });
    } catch {
      setFallback(true);
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.6));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.5;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    host.append(renderer.domElement);
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(33, 1, 0.1, 50);
    camera.position.set(0, 7.3, 7.4);
    camera.lookAt(0, 0.3, 0);
    scene.add(new THREE.HemisphereLight("#fff3d4", "#334332", 2.1));
    const sun = new THREE.DirectionalLight("#fff5db", 4.5);
    sun.position.set(-4, 7, 4);
    sun.castShadow = true;
    sun.shadow.mapSize.set(1024, 1024);
    sun.shadow.camera.left = -5;
    sun.shadow.camera.right = 5;
    sun.shadow.camera.top = 5;
    sun.shadow.camera.bottom = -5;
    sun.shadow.bias = -0.0005;
    sun.shadow.normalBias = 0.04;
    scene.add(sun);
    const fill = new THREE.DirectionalLight("#cde6c7", 0.7);
    fill.position.set(4, 3, -4);
    scene.add(fill);
    const ground = new THREE.Mesh(
      new THREE.PlaneGeometry(200, 200),
      new THREE.ShadowMaterial({ color: "#162313", opacity: 0.27 }),
    );
    ground.rotation.x = -Math.PI / 2;
    ground.position.y = -0.025;
    ground.receiveShadow = true;
    scene.add(ground);
    const meal = createMeal();
    scene.add(meal);
    let frame = 0;
    const render = () => {
      cancelAnimationFrame(frame);
      if (!document.hidden)
        frame = requestAnimationFrame(() => renderer.render(scene, camera));
    };
    const resize = () => {
      const width = host.clientWidth;
      const height = host.clientHeight;
      if (!width || !height) return;
      renderer.setSize(width, height);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      render();
    };
    const observer = new ResizeObserver(resize);
    observer.observe(host);
    const move = (event: PointerEvent) => {
      if (
        reducedMotion ||
        motionPreference.matches ||
        event.pointerType !== "mouse"
      )
        return;
      const bounds = host.getBoundingClientRect();
      meal.rotation.y =
        -0.2 + ((event.clientX - bounds.left) / bounds.width - 0.5) * 0.16;
      render();
    };
    host.addEventListener("pointermove", move);
    document.addEventListener("visibilitychange", render);
    resize();
    return () => {
      observer.disconnect();
      host.removeEventListener("pointermove", move);
      document.removeEventListener("visibilitychange", render);
      cancelAnimationFrame(frame);
      scene.traverse((object) => {
        if (object instanceof THREE.Mesh) {
          object.geometry.dispose();
          const materials = Array.isArray(object.material)
            ? object.material
            : [object.material];
          materials.forEach((material) => material.dispose());
        }
      });
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, [reducedMotion]);
  return (
    <div
      ref={container}
      className="three-scene"
      role="img"
      aria-label="Illustrative 3D bowl. This is an example scene, not a camera image."
    >
      {fallback && (
        <div className="scene-fallback">
          <span></span>
          <p>
            Your next meal,
            <br />a little clearer.
          </p>
        </div>
      )}
    </div>
  );
}
