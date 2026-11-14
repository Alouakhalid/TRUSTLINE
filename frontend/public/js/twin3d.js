/**
 * Interactive 3D Astronaut Digital Twin.
 * Powered by Three.js with Raycasting, anatomical sensor hotspots, and 2D SVG fallback.
 */

class AstronautDigitalTwin {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    if (!this.container) return;

    this.scene = null;
    this.camera = null;
    this.renderer = null;
    this.controls = null;
    this.astronautGroup = null;
    this.hotspotMeshes = [];
    this.selectedHotspot = null;
    this.raycaster = null;
    this.mouse = null;
    this.is2DFallback = false;
    this.sensorStatuses = {};

    this.init();
  }

  init() {
    if (typeof THREE === 'undefined') {
      console.warn('[3D Twin] Three.js not loaded, switching to 2D Anatomical Fallback.');
      this.render2DFallback();
      return;
    }

    try {
      this.initThree();
    } catch (e) {
      console.error('[3D Twin] WebGL initialization failed, rendering 2D Fallback:', e);
      this.render2DFallback();
    }
  }

  initThree() {
    const w = this.container.clientWidth || 600;
    const h = this.container.clientHeight || 480;

    // 1. Scene & Camera
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(45, w / h, 0.1, 100);
    this.camera.position.set(0, 0.6, 2.6);

    // 2. Renderer
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    this.renderer.setSize(w, h);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.domElement.className = 'twin-3d-canvas';
    this.container.innerHTML = '';
    this.container.appendChild(this.renderer.domElement);

    // 3. Lighting
    const ambLight = new THREE.AmbientLight(0x1a2b4c, 2.5);
    this.scene.add(ambLight);

    const cyanLight = new THREE.PointLight(0x00E5FF, 3.0, 10);
    cyanLight.position.set(2, 3, 2);
    this.scene.add(cyanLight);

    const violetLight = new THREE.PointLight(0x8B5CF6, 2.0, 10);
    violetLight.position.set(-2, -1, -2);
    this.scene.add(violetLight);

    // 4. OrbitControls
    if (typeof THREE.OrbitControls !== 'undefined') {
      this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
      this.controls.enableDamping = true;
      this.controls.dampingFactor = 0.05;
      this.controls.minDistance = 1.0;
      this.controls.maxDistance = 5.0;
      this.controls.maxPolarAngle = Math.PI / 2 + 0.3;
    }

    // 5. Build Anatomical Hologram Mannequin
    this.astronautGroup = new THREE.Group();
    this.buildAnatomicalModel();
    this.scene.add(this.astronautGroup);

    // 6. Sensor Hotspots
    this.createSensorHotspots();

    // 7. Raycaster for Interaction
    this.raycaster = new THREE.Raycaster();
    this.mouse = new THREE.Vector2();

    this.renderer.domElement.addEventListener('click', (e) => this.onCanvasClick(e));
    window.addEventListener('resize', () => this.onResize());

    this.animate();
  }

  buildAnatomicalModel() {
    // Holographic wireframe + rim shader material
    const suitMaterial = new THREE.MeshStandardMaterial({
      color: 0x0f224a,
      roughness: 0.3,
      metalness: 0.8,
      wireframe: false,
      transparent: true,
      opacity: 0.85
    });

    const wireframeMaterial = new THREE.MeshBasicMaterial({
      color: 0x00E5FF,
      wireframe: true,
      transparent: true,
      opacity: 0.25
    });

    const makePart = (geo, pos, scale = [1, 1, 1]) => {
      const mesh = new THREE.Mesh(geo, suitMaterial);
      const wire = new THREE.Mesh(geo, wireframeMaterial);
      mesh.position.set(...pos);
      wire.position.set(...pos);
      mesh.scale.set(...scale);
      wire.scale.set(...scale);
      this.astronautGroup.add(mesh);
      this.astronautGroup.add(wire);
      return mesh;
    };

    // Head / Helmet
    makePart(new THREE.SphereGeometry(0.18, 24, 24), [0, 0.82, 0]);
    // Visor
    const visorMat = new THREE.MeshPhysicalMaterial({ color: 0x00E5FF, metalness: 0.9, roughness: 0.1, transparent: true, opacity: 0.7 });
    const visor = new THREE.Mesh(new THREE.SphereGeometry(0.15, 16, 16, 0, Math.PI), visorMat);
    visor.position.set(0, 0.82, 0.07);
    visor.rotation.y = -Math.PI / 2;
    this.astronautGroup.add(visor);

    // Torso (Thorax + Abdomen)
    makePart(new THREE.CylinderGeometry(0.24, 0.19, 0.48, 18), [0, 0.42, 0]);
    makePart(new THREE.CylinderGeometry(0.19, 0.22, 0.30, 18), [0, 0.08, 0]);

    // Shoulders & Arms
    makePart(new THREE.SphereGeometry(0.11, 16, 16), [0.32, 0.58, 0]);
    makePart(new THREE.SphereGeometry(0.11, 16, 16), [-0.32, 0.58, 0]);
    // Right Arm (Upper & Forearm)
    makePart(new THREE.CylinderGeometry(0.08, 0.07, 0.30, 12), [0.36, 0.38, 0], [1, 1, 1]);
    makePart(new THREE.CylinderGeometry(0.07, 0.06, 0.28, 12), [0.42, 0.10, 0.05], [1, 1, 1]);
    // Left Arm (Upper & Forearm)
    makePart(new THREE.CylinderGeometry(0.08, 0.07, 0.30, 12), [-0.36, 0.38, 0], [1, 1, 1]);
    makePart(new THREE.CylinderGeometry(0.07, 0.06, 0.28, 12), [-0.42, 0.10, 0.05], [1, 1, 1]);

    // Hands
    makePart(new THREE.SphereGeometry(0.07, 12, 12), [0.46, -0.10, 0.06]);
    makePart(new THREE.SphereGeometry(0.07, 12, 12), [-0.46, -0.10, 0.06]);

    // Pelvis & Legs
    makePart(new THREE.CylinderGeometry(0.22, 0.20, 0.16, 16), [0, -0.14, 0]);
    // Right Leg
    makePart(new THREE.CylinderGeometry(0.09, 0.08, 0.42, 14), [0.14, -0.42, 0]);
    makePart(new THREE.CylinderGeometry(0.08, 0.07, 0.42, 14), [0.14, -0.82, 0.02]);
    makePart(new THREE.BoxGeometry(0.11, 0.08, 0.22), [0.14, -1.06, 0.06]);
    // Left Leg
    makePart(new THREE.CylinderGeometry(0.09, 0.08, 0.42, 14), [-0.14, -0.42, 0]);
    makePart(new THREE.CylinderGeometry(0.08, 0.07, 0.42, 14), [-0.14, -0.82, 0.02]);
    makePart(new THREE.BoxGeometry(0.11, 0.08, 0.22), [-0.14, -1.06, 0.06]);

    // Life Support Backpack (ECLSS / IMU mount)
    const backpack = new THREE.Mesh(new THREE.BoxGeometry(0.38, 0.46, 0.18), suitMaterial);
    backpack.position.set(0, 0.42, -0.18);
    this.astronautGroup.add(backpack);

    // Ground shadow plane
    const shadowGeo = new THREE.RingGeometry(0.2, 0.8, 32);
    const shadowMat = new THREE.MeshBasicMaterial({ color: 0x00E5FF, transparent: true, opacity: 0.12, side: THREE.DoubleSide });
    const shadow = new THREE.Mesh(shadowGeo, shadowMat);
    shadow.rotation.x = Math.PI / 2;
    shadow.position.y = -1.10;
    this.astronautGroup.add(shadow);
  }

  createSensorHotspots() {
    // 8 Genuine anatomical sensor locations
    const hotspotsConfig = [
      { id: 'ECG', name: 'Thoracic ECG (3-Lead)', pos: [-0.06, 0.48, 0.23], color: 0x10B981, desc: 'Lead II bioelectrodes tracking cardiac depolarization.' },
      { id: 'RESPIRATION', name: 'RIP Respiration Belt', pos: [0.0, 0.28, 0.22], color: 0x00E5FF, desc: 'Inductive chest expansion belt measuring breathing rate.' },
      { id: 'CORE_TEMP', name: 'Core Temperature Estimator', pos: [0.0, 0.14, 0.19], color: 0x8B5CF6, desc: 'Deep-body visceral heat-flux thermometry.' },
      { id: 'SKIN_TEMP', name: 'Skin Surface Thermistor', pos: [-0.43, 0.02, 0.06], color: 0x3B82F6, desc: 'Inner wrist contact thermistor measuring peripheral heat.' },
      { id: 'PPG', name: 'Photoplethysmogram (PPG)', pos: [0.43, 0.02, 0.06], color: 0x00E5FF, desc: 'Optical plethysmography measuring volumetric blood pulse.' },
      { id: 'SPO2', name: 'Arterial SpO2 Sensor', pos: [-0.47, -0.10, 0.07], color: 0x10B981, desc: 'Finger spectrophotometry estimating arterial O2 saturation.' },
      { id: 'EDA', name: 'Galvanic Skin Conductance (EDA)', pos: [0.47, -0.10, 0.07], color: 0xF59E0B, desc: 'Palmar electrodes tracking sympathetic nervous arousal.' },
      { id: 'ACCELEROMETER', name: '3-Axis IMU & Gyroscope', pos: [0.0, 0.45, -0.28], color: 0x3B82F6, desc: 'Suit backpack MEMS inertial sensor tracking body kinematics.' }
    ];

    for (const h of hotspotsConfig) {
      const group = new THREE.Group();
      group.position.set(...h.pos);

      // Core glowing sphere
      const sphereMat = new THREE.MeshBasicMaterial({ color: h.color });
      const sphere = new THREE.Mesh(new THREE.SphereGeometry(0.032, 16, 16), sphereMat);
      group.add(sphere);

      // Outer pulsing ring
      const ringMat = new THREE.MeshBasicMaterial({ color: h.color, wireframe: true, transparent: true, opacity: 0.6 });
      const ring = new THREE.Mesh(new THREE.RingGeometry(0.045, 0.075, 24), ringMat);
      ring.rotation.x = Math.PI / 2;
      group.add(ring);

      group.userData = h;
      group.ringMesh = ring;
      this.astronautGroup.add(group);
      this.hotspotMeshes.push(group);
    }
  }

  updateHotspotQuality(sensorType, qualityStatus) {
    for (const h of this.hotspotMeshes) {
      if (h.userData.id === sensorType) {
        let colorHex = 0x10B981; // Nominal
        if (qualityStatus === 'DEGRADED' || qualityStatus === 'WARNING') colorHex = 0xF59E0B;
        if (qualityStatus === 'CRITICAL' || qualityStatus === 'FAULT') colorHex = 0xEF4444;

        h.children[0].material.color.setHex(colorHex);
        h.ringMesh.material.color.setHex(colorHex);
      }
    }
  }

  onCanvasClick(event) {
    const rect = this.renderer.domElement.getBoundingClientRect();
    this.mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    this.mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    this.raycaster.setFromCamera(this.mouse, this.camera);
    const intersects = this.raycaster.intersectObjects(this.hotspotMeshes, true);

    if (intersects.length > 0) {
      let current = intersects[0].object;
      while (current && !current.userData.id && current.parent) {
        current = current.parent;
      }
      if (current && current.userData.id) {
        this.selectHotspot(current.userData);
      }
    }
  }

  selectHotspot(hotspotData) {
    this.selectedHotspot = hotspotData;
    window.dispatchEvent(new CustomEvent('hotspot-selected', { detail: hotspotData }));
  }

  onResize() {
    if (!this.container || !this.renderer || !this.camera) return;
    const w = this.container.clientWidth;
    const h = this.container.clientHeight;
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(w, h);
  }

  animate() {
    requestAnimationFrame(() => this.animate());
    const time = Date.now() * 0.003;

    // Pulse hotspot rings
    for (const h of this.hotspotMeshes) {
      if (h.ringMesh) {
        const s = 1.0 + 0.25 * Math.sin(time * 3.0);
        h.ringMesh.scale.set(s, s, s);
      }
    }

    if (this.controls) this.controls.update();
    if (this.renderer && this.scene && this.camera) {
      this.renderer.render(this.scene, this.camera);
    }
  }

  render2DFallback() {
    this.is2DFallback = true;
    this.container.innerHTML = `
      <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; height:100%; padding:20px; text-align:center;">
        <div style="font-weight:700; color:var(--color-cyan); margin-bottom:10px; font-size:14px;">
          2D ANATOMICAL SENSOR MAP (WebGL Fallback Active)
        </div>
        <svg viewBox="0 0 300 480" width="220" height="380" style="filter: drop-shadow(0 0 12px rgba(0,229,255,0.2));">
          <!-- Body Silhouette -->
          <circle cx="150" cy="50" r="32" fill="#0d1f42" stroke="#00E5FF" stroke-width="1.5" />
          <path d="M 120 90 L 180 90 L 170 240 L 130 240 Z" fill="#0d1f42" stroke="#00E5FF" stroke-width="1.5" />
          <!-- Arms -->
          <path d="M 120 95 L 80 180 L 70 230" fill="none" stroke="#00E5FF" stroke-width="8" stroke-linecap="round" />
          <path d="M 180 95 L 220 180 L 230 230" fill="none" stroke="#00E5FF" stroke-width="8" stroke-linecap="round" />
          <!-- Legs -->
          <path d="M 135 240 L 130 360 L 125 430" fill="none" stroke="#00E5FF" stroke-width="10" stroke-linecap="round" />
          <path d="M 165 240 L 170 360 L 175 430" fill="none" stroke="#00E5FF" stroke-width="10" stroke-linecap="round" />

          <!-- Sensor Hotspots 2D -->
          <circle cx="140" cy="130" r="8" fill="#10B981" class="hotspot-2d" onclick="window.twin.selectHotspot({id:'ECG', name:'Thoracic ECG (3-Lead)', desc:'Thoracic electrodes measuring cardiac depolarization.'})" style="cursor:pointer;" />
          <text x="140" y="115" fill="#10B981" font-size="9" text-anchor="middle" font-family="monospace">ECG</text>

          <circle cx="150" cy="165" r="7" fill="#00E5FF" class="hotspot-2d" onclick="window.twin.selectHotspot({id:'RESPIRATION', name:'RIP Respiration Belt', desc:'Chest expansion belt.'})" style="cursor:pointer;" />
          <text x="150" y="185" fill="#00E5FF" font-size="9" text-anchor="middle" font-family="monospace">RESP</text>

          <circle cx="150" cy="195" r="7" fill="#8B5CF6" class="hotspot-2d" onclick="window.twin.selectHotspot({id:'CORE_TEMP', name:'Core Body Temperature', desc:'Deep body core heat-flux.'})" style="cursor:pointer;" />
          <text x="150" y="210" fill="#8B5CF6" font-size="9" text-anchor="middle" font-family="monospace">CORE</text>

          <circle cx="72" cy="225" r="6" fill="#3B82F6" class="hotspot-2d" onclick="window.twin.selectHotspot({id:'SKIN_TEMP', name:'Skin Surface Temp', desc:'Wrist thermistor.'})" style="cursor:pointer;" />
          <circle cx="68" cy="245" r="6" fill="#10B981" class="hotspot-2d" onclick="window.twin.selectHotspot({id:'SPO2', name:'Arterial SpO2', desc:'Finger pulse oximeter.'})" style="cursor:pointer;" />

          <circle cx="228" cy="225" r="6" fill="#00E5FF" class="hotspot-2d" onclick="window.twin.selectHotspot({id:'PPG', name:'Optical PPG', desc:'Wrist plethysmography.'})" style="cursor:pointer;" />
          <circle cx="232" cy="245" r="6" fill="#F59E0B" class="hotspot-2d" onclick="window.twin.selectHotspot({id:'EDA', name:'Electrodermal Activity', desc:'Palmar skin conductance.'})" style="cursor:pointer;" />
        </svg>
      </div>
    `;
  }
}

window.AstronautDigitalTwin = AstronautDigitalTwin;
