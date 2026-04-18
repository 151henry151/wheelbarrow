/**
 * Wheelbarrow — Three.js WebGL renderer (perspective + follow camera).
 * World: game tile (x, y) maps to scene position (x*T+T/2, z, y*T+T/2) with Y up.
 */
/* global THREE, Terrain */
const Renderer = (() => {
  const T = 32;
  /** Road planes extend past tile edges (tile pitch is {@link T}) so cardinally-adjacent paths read as one ribbon. */
  const ROAD_TILE_OVERLAP = 14;
  /** Rebuilding the terrain mesh every frame tanked FPS; grass follows this cadence while the camera stays smooth. */
  const GRASS_REBUILD_MS = 110;
  /** Water plane is larger than a tile so shader can draw fillets past |p|=1 onto grass. */
  const WATER_QUAD_SCALE = 1.42;

  /** Clear-color / upper sky (distinct from grass so tilt reads as sky vs ground). */
  const SEASON_SKY = {
    spring: 0x8ec0e8,
    summer: 0x7ab8ec,
    fall:   0xc8b898,
    winter: 0xa8b8c8,
  };
  /** Base FogExp2 density when camera pitch is mostly top-down (see `_applySeasonAtmosphere`). */
  const FOG_DENSITY_TOPDOWN = 0.00016;
  /** Fog tints distant terrain toward horizon — keep close to sky for a natural horizon line. */
  const SEASON_FOG = {
    spring: 0x7aa8c0,
    summer: 0x6a98b8,
    fall:   0xa89878,
    winter: 0x8898a8,
  };
  const TOWN_HEX = [
    0x6a8aff, 0x6affa0, 0xffa06a, 0xff6a9a, 0xa06aff,
    0x6affff, 0xffff6a, 0xff9a6a, 0x6aff8a, 0x9a6aff,
  ];

  let canvas;
  let renderer;
  let scene;
  let camera;
  let s;
  let amb;
  let sun;
  let hemi;
  let groundGroup;
  /** Solid grass-colored plane under detail tiles — fog disabled so horizon stays green. */
  let horizonGrass;
  let grassMesh;
  let grassMat;
  /** Max land tiles in the grass disk (~π r²); mesh vertex budget scales with this. */
  const MAX_GRASS = 10000;
  /** Radial fade band at grass edge (world units ≈ tiles × T). */
  const GRASS_FADE_TILES = 14;
  const HORIZON_PLANE_SIZE = 340000;
  let waterMesh;
  let waterMat;
  const MAX_WATER = 12000;
  let roadMesh;
  let roadMat;
  const MAX_ROAD = 12000;
  let dynamicRoot;
  let overlayRoot;

  /** Orbit pitch (rad): 0 = horizon ring around target, π/2 = straight above. */
  const PITCH_MIN = 0.06;
  const PITCH_MAX = 1.52;
  const DIST_MIN = 180;
  const DIST_MAX = 1600;

  let _camYaw = 0.55;
  let _camPitch = 0.88;
  let _camDist = 380;
  let _dragging = false;
  let _lastPtrX = 0;
  let _lastPtrY = 0;

  let _camX = 0;
  let _camY = 0;
  let _vpW = 0;
  let _vpH = 0;
  let _lastGrassBuildMs = 0;

  /** Created in init() so this file never touches THREE before three.min.js runs. */
  let _dummy;
  let _c;
  let _raycaster;
  let _planeHit;
  const nodePool = [];
  let nodePoolUsed = 0;
  const pilePool = [];
  let pilePoolUsed = 0;
  const cropPool = [];
  let cropPoolUsed = 0;
  const wbPool = [];
  let wbPoolUsed = 0;

  function _fieldGrassRgb(tx, ty) {
    const fx = tx * 0.17;
    const fy = ty * 0.21;
    const n =
      Math.sin(fx + fy * 0.73) * 0.42 +
      Math.cos(fx * 0.65 - fy * 0.88) * 0.36 +
      Math.sin((tx + ty) * 0.095) * 0.28;
    const t = (n + 1.06) / 2.12;
    return {
      r: (46 + t * 14) / 255,
      g: (68 + t * 16) / 255,
      b: (38 + t * 12) / 255,
    };
  }

  /** Same palette as {@link _fieldGrassRgb} but sampled in **world XZ** so colors do not jump at tile edges. */
  function _grassRgbContinuous(worldX, worldZ) {
    const fx = worldX * 0.0053125;
    const fy = worldZ * 0.0065625;
    const n =
      Math.sin(fx + fy * 0.73) * 0.42 +
      Math.cos(fx * 0.65 - fy * 0.88) * 0.36 +
      Math.sin((worldX + worldZ) * 0.00296875) * 0.28;
    const t = (n + 1.06) / 2.12;
    return {
      r: (46 + t * 14) / 255,
      g: (68 + t * 16) / 255,
      b: (38 + t * 12) / 255,
    };
  }

  function _shadeRgb(o, dr, dg, db) {
    _c.setRGB(
      Math.min(1, Math.max(0, o.r + dr / 255)),
      Math.min(1, Math.max(0, o.g + dg / 255)),
      Math.min(1, Math.max(0, o.b + db / 255)),
    );
    return _c.clone();
  }

  function _seasonName() {
    return (s.season && s.season.name) || 'spring';
  }

  function _applySeasonAtmosphere() {
    const name = _seasonName();
    const sky = SEASON_SKY[name] ?? SEASON_SKY.spring;
    const fg = SEASON_FOG[name] ?? SEASON_FOG.spring;
    scene.background = new THREE.Color(sky);
    // FogExp2 uses distance along the view ray. At shallow pitch (near horizontal), rays to the
    // ground are much longer than in top-down view, so the same density whites out terrain. Scale
    // density by orbit pitch so low angles stay visible; full strength near top-down.
    const t =
      (PITCH_MAX > PITCH_MIN)
        ? (_camPitch - PITCH_MIN) / (PITCH_MAX - PITCH_MIN)
        : 1;
    const u = Math.max(0, Math.min(1, t));
    let density = FOG_DENSITY_TOPDOWN * (0.06 + 0.94 * Math.pow(u, 1.15));
    // Far camera + shallow pitch: long view rays through fog; ease more when zoomed out.
    const distEase = Math.min(1.35, Math.max(0.28, DIST_MIN / Math.max(DIST_MIN, _camDist)));
    density *= distEase;
    scene.fog = new THREE.FogExp2(fg, density);
    // Fixed “high noon” fill — do not dim by season (sky/fog tint still follow season above).
    if (hemi && amb) {
      hemi.color.setHex(0xd8ecff);
      hemi.groundColor.setHex(0x98a898);
      hemi.intensity = 0.78;
      amb.color.setHex(0xeff6ff);
      amb.intensity = 0.58;
    }
    if (sun) {
      sun.color.setHex(0xffffff);
      sun.intensity = 1.82;
    }
  }

  function init(c, st) {
    canvas = c;
    s = st;
    if (typeof THREE === 'undefined') {
      console.error('Wheelbarrow: THREE is not loaded (check vendor/three.min.js).');
      return;
    }
    _dummy = new THREE.Object3D();
    _c = new THREE.Color();
    _planeHit = new THREE.Vector3();
    _raycaster = new THREE.Raycaster();
    scene = new THREE.Scene();

    camera = new THREE.PerspectiveCamera(48, 1, 2, 12000);
    camera.up.set(0, 1, 0);

    renderer = new THREE.WebGLRenderer({
      canvas,
      antialias: true,
      alpha: false,
      powerPreference: 'high-performance',
    });
    if (!renderer.getContext()) {
      console.error('Wheelbarrow: WebGL context creation failed.');
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    if (THREE.SRGBColorSpace !== undefined) {
      renderer.outputColorSpace = THREE.SRGBColorSpace;
    }
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.32;

    amb = new THREE.AmbientLight(0xeff6ff, 0.58);
    scene.add(amb);
    hemi = new THREE.HemisphereLight(0xd8ecff, 0x98a898, 0.78);
    scene.add(hemi);
    sun = new THREE.DirectionalLight(0xffffff, 1.82);
    sun.position.set(420, 1250, 280);
    sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048);
    sun.shadow.camera.near = 100;
    sun.shadow.camera.far = 3200;
    sun.shadow.camera.left = -1400;
    sun.shadow.camera.right = 1400;
    sun.shadow.camera.top = 1400;
    sun.shadow.camera.bottom = -1400;
    scene.add(sun);

    _applySeasonAtmosphere();

    groundGroup = new THREE.Group();
    scene.add(groundGroup);

    const hzCol = new THREE.Color();
    hzCol.setRGB(0.22, 0.32, 0.2);
    horizonGrass = new THREE.Mesh(
      new THREE.PlaneGeometry(HORIZON_PLANE_SIZE, HORIZON_PLANE_SIZE),
      new THREE.MeshLambertMaterial({
        color: hzCol,
        fog: false,
        depthWrite: false,
      }),
    );
    horizonGrass.rotation.x = -Math.PI / 2;
    horizonGrass.renderOrder = -20;
    groundGroup.add(horizonGrass);

    grassMat = new THREE.MeshLambertMaterial({ vertexColors: true, fog: false });
    grassMesh = new THREE.Mesh(new THREE.BufferGeometry(), grassMat);
    grassMesh.receiveShadow = true;
    grassMesh.castShadow = false;
    grassMesh.renderOrder = 0;
    groundGroup.add(grassMesh);

    const waterGeo = new THREE.PlaneGeometry(T * WATER_QUAD_SCALE, T * WATER_QUAD_SCALE);
    waterGeo.rotateX(-Math.PI / 2);
    // Per-instance corner radii for IQ sdRoundBox: vec4 = (NE, SE, NW, SW) — see pushW.
    waterGeo.setAttribute(
      'aWaterR',
      new THREE.InstancedBufferAttribute(new Float32Array(MAX_WATER * 4), 4),
    );
    // Inner L-vertex fillets: vec4 (NE,SE,NW,SW) — shader subtracts a disk cap (concave arc), not union into grass.
    waterGeo.setAttribute(
      'aInnerFillet',
      new THREE.InstancedBufferAttribute(new Float32Array(MAX_WATER * 4), 4),
    );
    waterMat = new THREE.MeshBasicMaterial({
      color: 0x4ec8ff,
      fog: false,
      toneMapped: false,
      polygonOffset: true,
      polygonOffsetFactor: -1,
      polygonOffsetUnits: -1,
    });
    if (THREE.SRGBColorSpace !== undefined) {
      waterMat.colorSpace = THREE.SRGBColorSpace;
    }
    // Analytical rounded rect in UV space — inject SDF discard only; keep default MeshBasic tail
    // (opaque / tonemapping / colorspace chunks). Replacing the whole fragment shader skipped
    // linearToOutputTexel and produced wrong hues (often reading as green vs grass).
    waterMat.onBeforeCompile = (shader) => {
      shader.vertexShader = shader.vertexShader.replace(
        '#include <common>',
        `#include <common>
attribute vec4 aWaterR;
attribute vec4 aInnerFillet;
varying vec4 vWaterR;
varying vec4 vInnerFillet;
varying vec2 vWaterUv;
`,
      );
      shader.vertexShader = shader.vertexShader.replace(
        '#include <uv_vertex>',
        `#include <uv_vertex>
vWaterR = aWaterR;
vInnerFillet = aInnerFillet;
vWaterUv = uv;
`,
      );
      const sdRoundBoxFn = `
// https://iquilezles.org/articles/distfunctions2d/ — vec4 = (NE, SE, NW, SW); p in [-1,1]^2
float sdRoundBox( vec2 p, vec2 b, vec4 r ) {
  r.xy = (p.x>0.0)?r.xy : r.zw;
  r.x  = (p.y>0.0)?r.x  : r.y;
  vec2 q = abs(p)-b+r.x;
  return min(max(q.x,q.y),0.0) + length(max(q,0.0)) - r.x;
}
// Smooth max — concave inner corners subtract a disk cap; smax avoids a crease vs sdRoundBox.
float smax( float a, float b, float k ) {
  float h = clamp( 0.5 + 0.5 * ( a - b ) / k, 0.0, 1.0 );
  return mix( b, a, h ) + k * h * ( 1.0 - h );
}
`;
      shader.fragmentShader = shader.fragmentShader.replace(
        '#include <clipping_planes_pars_fragment>',
        `#include <clipping_planes_pars_fragment>
varying vec4 vWaterR;
varying vec4 vInnerFillet;
varying vec2 vWaterUv;
${sdRoundBoxFn}`,
      );
      const wqs = WATER_QUAD_SCALE.toFixed(4);
      shader.fragmentShader = shader.fragmentShader.replace(
        '#include <clipping_planes_fragment>',
        `#include <clipping_planes_fragment>
	float wsm = 0.045;
	float wqs = ${wqs};
	// Must match sdRoundBox half-extents vec2(1.028) — centers for inner (concave) fillet disks sit in grass past each corner.
	float B = 1.028;
	float Rf = 1.0;
	// Offset along diagonal from each tile corner into grass so |corner - O| = Rf (tangent fillet); full (B+Rf,B+Rf) misses the corner.
	float od = Rf * 0.70710678;
	vec2 puvW = (vWaterUv - 0.5) * 2.0 * wqs;
	float dw = sdRoundBox( puvW, vec2( B ), vWaterR );
	// Inner L-corners: subtract water with smax(dw, Rf - |p-O|); O is in grass on the angle bisector from each corner.
	float sfk = 0.09;
	if ( vInnerFillet.x > 0.5 ) {
		float dcut = Rf - length( puvW - vec2( B + od, B + od ) );
		dw = smax( dw, dcut, sfk );
	}
	if ( vInnerFillet.y > 0.5 ) {
		float dcut = Rf - length( puvW - vec2( B + od, -B - od ) );
		dw = smax( dw, dcut, sfk );
	}
	if ( vInnerFillet.z > 0.5 ) {
		float dcut = Rf - length( puvW - vec2( -B - od, B + od ) );
		dw = smax( dw, dcut, sfk );
	}
	if ( vInnerFillet.w > 0.5 ) {
		float dcut = Rf - length( puvW - vec2( -B - od, -B - od ) );
		dw = smax( dw, dcut, sfk );
	}
	if ( dw > wsm ) discard;
`,
      );
    };
    waterMesh = new THREE.InstancedMesh(waterGeo, waterMat, MAX_WATER);
    waterMesh.receiveShadow = false;
    waterMesh.renderOrder = 2;
    waterMesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    groundGroup.add(waterMesh);

    // Flat dirt ribbon (XZ plane) — reads as a path, not a tall block on every tile.
    const roadGeo = new THREE.PlaneGeometry(T + ROAD_TILE_OVERLAP, T + ROAD_TILE_OVERLAP);
    roadMat = new THREE.MeshLambertMaterial({ color: 0x5c4334, emissive: 0x120c08, emissiveIntensity: 0.35 });
    roadMat.polygonOffset = true;
    roadMat.polygonOffsetFactor = -1;
    roadMat.polygonOffsetUnits = -3;
    roadMesh = new THREE.InstancedMesh(roadGeo, roadMat, MAX_ROAD);
    roadMesh.receiveShadow = true;
    roadMesh.castShadow = false;
    roadMesh.renderOrder = 1;
    roadMesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    groundGroup.add(roadMesh);

    dynamicRoot = new THREE.Group();
    scene.add(dynamicRoot);
    overlayRoot = new THREE.Group();
    scene.add(overlayRoot);

    resize();
    window.addEventListener('resize', resize);

    canvas.addEventListener('mousedown', (e) => {
      if (e.button === 0) {
        _dragging = true;
        _lastPtrX = e.clientX;
        _lastPtrY = e.clientY;
      }
    });
    window.addEventListener('mouseup', () => { _dragging = false; });
    window.addEventListener('mousemove', (e) => {
      if (!_dragging) return;
      const dx = e.clientX - _lastPtrX;
      const dy = e.clientY - _lastPtrY;
      _lastPtrX = e.clientX;
      _lastPtrY = e.clientY;
      // Yaw orbit only while stationary (no arrow keys / autopilot); pitch always user-controlled
      if (!s.cameraFollowDriving) {
        _camYaw += dx * 0.0045;
      }
      // Drag up → more top-down; drag down → flatter toward horizon
      _camPitch -= dy * 0.0045;
      _camPitch = Math.max(PITCH_MIN, Math.min(PITCH_MAX, _camPitch));
    });
    canvas.addEventListener('wheel', (e) => {
      e.preventDefault();
      const step = e.deltaY > 0 ? 28 : -28;
      _camDist = Math.max(DIST_MIN, Math.min(DIST_MAX, _camDist + step));
    }, { passive: false });
    window.addEventListener('keydown', (e) => {
      if (e.key === '[') _camPitch = Math.min(PITCH_MAX, _camPitch + 0.05);
      if (e.key === ']') _camPitch = Math.max(PITCH_MIN, _camPitch - 0.05);
    });
  }

  function resize() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    const W = canvas.width;
    const H = canvas.height;
    if (!camera || !renderer) return;
    camera.aspect = W / H;
    camera.updateProjectionMatrix();
    renderer.setSize(W, H, false);
    if (s && s.player) draw();
  }

  function _worldXZ(gx, gy) {
    return { x: gx * T + T / 2, z: gy * T + T / 2 };
  }

  function _groundY(tx, ty) {
    if (typeof Terrain !== 'undefined') return Terrain.worldYFloat(tx, ty);
    return 0;
  }

  function _lerpAngleRad(from, to, t) {
    let d = to - from;
    while (d > Math.PI) d -= 2 * Math.PI;
    while (d < -Math.PI) d += 2 * Math.PI;
    return from + d * t;
  }

  function _updateCamera(px, py) {
    const { x: tx, z: tz } = _worldXZ(px, py);
    if (
      s.cameraFollowDriving
      && s.player
      && Number.isFinite(s.player.angle)
    ) {
      // Behind wheelbarrow: horizontal offset aligns with −(cos θ, sin θ) in XZ → yaw = atan2(-cos θ, -sin θ)
      const targetYaw = Math.atan2(-Math.cos(s.player.angle), -Math.sin(s.player.angle));
      // Slightly snappier return when re-engaging control so “behind barrow” reads clearly
      _camYaw = _lerpAngleRad(_camYaw, targetYaw, 0.32);
    }
    const cp = Math.cos(_camPitch);
    const sp = Math.sin(_camPitch);
    const cy = Math.cos(_camYaw);
    const sy = Math.sin(_camYaw);
    const offX = _camDist * cp * sy;
    const offZ = _camDist * cp * cy;
    const offY = _camDist * sp;
    camera.position.set(tx + offX, offY, tz + offZ);
    const aimY = _groundY(px, py) + 12;
    camera.lookAt(tx, aimY, tz);
  }

  /**
   * Horizontal basis in world XZ (tile x → +X, tile y → +Z) for camera-relative steering.
   * Forward = into the view (from camera toward the wheelbarrow, then continuing past them).
   * Down arrow uses -forward (toward the camera / screen-bottom feel).
   */
  function getCameraMoveBasis() {
    const cp = Math.cos(_camPitch);
    const cy = Math.cos(_camYaw);
    const sy = Math.sin(_camYaw);
    const offX = _camDist * cp * sy;
    const offZ = _camDist * cp * cy;
    let fx = -offX;
    let fz = -offZ;
    const flen = Math.hypot(fx, fz);
    if (flen < 1e-8) {
      fx = 0;
      fz = -1;
    } else {
      fx /= flen;
      fz /= flen;
    }
    const rx = -fz;
    const rz = fx;
    return { fx, fz, rx, rz };
  }

  /** Server movement angle (east=0, south=π/2): horizontal view direction into the screen. */
  function getCameraFacingAngle() {
    const { fx, fz } = getCameraMoveBasis();
    return Math.atan2(fz, fx);
  }

  const _NDC_FRUSTUM_SAMPLES = [
    [-1, -1], [1, -1], [1, 1], [-1, 1],
    [0, -1], [1, 0], [0, 1], [-1, 0], [0, 0],
  ];

  /**
   * Intersection of a world ray with y = planeY, or a far point along horizontal view for horizon skimming.
   * Ensures frustum samples always contribute when {@link THREE.Ray#intersectPlane} misses (shallow pitch).
   */
  function _rayGroundSample(r, planeY, out) {
    const oy = r.origin.y;
    const dy = r.direction.y;
    const eps = 1e-5;
    if (Math.abs(dy) > eps) {
      const t = (planeY - oy) / dy;
      if (t > 0) {
        out.copy(r.origin).addScaledVector(r.direction, t);
        return;
      }
    }
    const dx = r.direction.x;
    const dz = r.direction.z;
    const hlen = Math.hypot(dx, dz);
    const dist = Math.min((camera && camera.far) ? camera.far * 0.92 : 11000, 11000);
    if (hlen < eps) {
      out.set(r.origin.x, planeY, r.origin.z);
      return;
    }
    out.set(
      r.origin.x + (dx / hlen) * dist,
      planeY,
      r.origin.z + (dz / hlen) * dist,
    );
  }

  /**
   * Tile indices (inclusive) whose ground may appear in the current view.
   * Uses frustum vs ground plane — the old canvas-pixel rect was wrong for perspective and caused diagonal cutoffs.
   */
  function _visibleTileRange(wx, wy, px, py) {
    if (!_raycaster || !camera || !_planeHit) return null;
    const planeY = _groundY(px, py);
    const pcx = px * T + T / 2;
    const pcz = py * T + T / 2;
    let minX = pcx;
    let maxX = pcx;
    let minZ = pcz;
    let maxZ = pcz;
    camera.updateMatrixWorld(true);
    for (let i = 0; i < _NDC_FRUSTUM_SAMPLES.length; i++) {
      const nx = _NDC_FRUSTUM_SAMPLES[i][0];
      const ny = _NDC_FRUSTUM_SAMPLES[i][1];
      _raycaster.setFromCamera(new THREE.Vector2(nx, ny), camera);
      _rayGroundSample(_raycaster.ray, planeY, _planeHit);
      minX = Math.min(minX, _planeHit.x);
      maxX = Math.max(maxX, _planeHit.x);
      minZ = Math.min(minZ, _planeHit.z);
      maxZ = Math.max(maxZ, _planeHit.z);
    }
    const margin = T * 1.5;
    minX -= margin;
    maxX += margin;
    minZ -= margin;
    maxZ += margin;
    const sx = Math.max(0, Math.floor(minX / T));
    const sy = Math.max(0, Math.floor(minZ / T));
    const ex = Math.min(wx - 1, Math.floor(maxX / T));
    const ey = Math.min(wy - 1, Math.floor(maxZ / T));
    if (ex < sx || ey < sy) return null;
    return { sx, sy, ex, ey };
  }

  /**
   * Frustum ∩ ground plane can under-estimate which tiles are needed at shallow pitch or on hills.
   * Union with a player-centered footprint so roads/water/soil don’t vanish when orbiting the camera.
   */
  function _expandTileRangeForGroundLayers(sx, sy, ex, ey, wx, wy, px, py) {
    // Tighter than before: large span + pad was loading far beyond the frustum and costing CPU.
    const span = 26 + Math.min(42, Math.floor(_camDist / T));
    const u0 = Math.max(0, Math.floor(px) - span);
    const v0 = Math.max(0, Math.floor(py) - span);
    const u1 = Math.min(wx - 1, Math.ceil(px) + span);
    const v1 = Math.min(wy - 1, Math.ceil(py) + span);
    const pad = 8;
    let sx2 = Math.min(sx, u0) - pad;
    let sy2 = Math.min(sy, v0) - pad;
    let ex2 = Math.max(ex, u1) + pad;
    let ey2 = Math.max(ey, v1) + pad;
    sx2 = Math.max(0, sx2);
    sy2 = Math.max(0, sy2);
    ex2 = Math.min(wx - 1, ex2);
    ey2 = Math.min(wy - 1, ey2);
    if (ex2 < sx2 || ey2 < sy2) {
      return { sx: 0, sy: 0, ex: wx - 1, ey: wy - 1 };
    }
    return { sx: sx2, sy: sy2, ex: ex2, ey: ey2 };
  }

  function _smoothstep01(edge0, edge1, x) {
    const t = Math.max(0, Math.min(1, (x - edge0) / (edge1 - edge0)));
    return t * t * (3 - 2 * t);
  }

  /**
   * Smooth grass terrain: indexed mesh with height = Terrain.worldYFloat at each vertex.
   * Skips water tiles (same footprint as before). SUB=2 when the bbox is small enough.
   */
  function _setGrassTiles(px, py, wx, wy, hzR, hzG, hzB) {
    const rTiles = Math.sqrt(MAX_GRASS / Math.PI);
    const rFade0 = Math.max(0, rTiles - GRASS_FADE_TILES);
    const waterKey = new Set((s.water_tiles || []).map((w) => `${w.x},${w.y}`));
    const bbox = Math.ceil(rTiles) + 2;
    const tcx = Math.floor(px);
    const tcy = Math.floor(py);

    let minTx = Infinity;
    let maxTx = -Infinity;
    let minTy = Infinity;
    let maxTy = -Infinity;
    let anyLand = false;
    for (let ty = tcy - bbox; ty <= tcy + bbox; ty++) {
      for (let tx = tcx - bbox; tx <= tcx + bbox; tx++) {
        if (tx < 0 || ty < 0 || tx >= wx || ty >= wy) continue;
        const dist = Math.hypot(tx + 0.5 - px, ty + 0.5 - py);
        if (dist > rTiles) continue;
        if (waterKey.has(`${tx},${ty}`)) continue;
        anyLand = true;
        minTx = Math.min(minTx, tx);
        maxTx = Math.max(maxTx, tx);
        minTy = Math.min(minTy, ty);
        maxTy = Math.max(maxTy, ty);
      }
    }

    if (grassMesh.geometry) grassMesh.geometry.dispose();

    if (!anyLand || !Number.isFinite(minTx)) {
      grassMesh.geometry = new THREE.BufferGeometry();
      grassMesh.visible = false;
      return;
    }
    grassMesh.visible = true;

    const Wt = maxTx - minTx + 1;
    const Ht = maxTy - minTy + 1;
    const SUB = Wt * Ht > 4200 ? 1 : 2;
    const nx = Wt * SUB;
    const ny = Ht * SUB;
    const vCount = (nx + 1) * (ny + 1);
    const positions = new Float32Array(vCount * 3);
    const colors = new Float32Array(vCount * 3);
    const idxRow = nx + 1;

    for (let j = 0; j <= ny; j++) {
      for (let i = 0; i <= nx; i++) {
        const gx = minTx - 0.5 + i / SUB;
        const gy = minTy - 0.5 + j / SUB;
        const wxp = gx * T + T / 2;
        const wzp = gy * T + T / 2;
        const y = Terrain.worldYFloat(gx, gy);
        const p = (j * idxRow + i) * 3;
        positions[p] = wxp;
        positions[p + 1] = y;
        positions[p + 2] = wzp;
        const dist = Math.hypot(gx - px, gy - py);
        const base = _grassRgbContinuous(wxp, wzp);
        const shade = 1 - 0.035 * Math.sin(wxp * 0.031) * Math.sin(wzp * 0.029);
        const edgeBlend = _smoothstep01(rFade0, rTiles, dist);
        colors[p] = base.r * shade * (1 - edgeBlend) + hzR * edgeBlend;
        colors[p + 1] = base.g * shade * (1 - edgeBlend) + hzG * edgeBlend;
        colors[p + 2] = base.b * shade * (1 - edgeBlend) + hzB * edgeBlend;
      }
    }

    const indices = [];
    for (let j = 0; j < ny; j++) {
      for (let i = 0; i < nx; i++) {
        const tx = minTx + Math.floor(i / SUB);
        const ty = minTy + Math.floor(j / SUB);
        if (tx < 0 || ty < 0 || tx >= wx || ty >= wy) continue;
        if (waterKey.has(`${tx},${ty}`)) continue;
        if (Math.hypot(tx + 0.5 - px, ty + 0.5 - py) > rTiles) continue;
        const a = j * idxRow + i;
        const b = a + 1;
        const d = a + idxRow;
        const c = d + 1;
        indices.push(a, b, d, b, c, d);
      }
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    if (indices.length) {
      geo.setIndex(indices);
    }
    geo.computeVertexNormals();
    grassMesh.geometry = geo;
  }

  function _waterAndRoadsInView(sx, sy, ex, ey) {
    let wi = 0;
    let ri = 0;
    const waterSet = new Set((s.water_tiles || []).map((w) => `${w.x},${w.y}`));
    const hasW = (x, y) => waterSet.has(`${x},${y}`);
    const waterRAttr = waterMesh.geometry.getAttribute('aWaterR');
    const waterRArr = waterRAttr.array;
    const waterFilletAttr = waterMesh.geometry.getAttribute('aInnerFillet');
    const waterFilletArr = waterFilletAttr.array;
    const pushW = (tx, ty) => {
      if (wi >= MAX_WATER) return;
      const { x, z } = _worldXZ(tx, ty);
      _dummy.position.set(x, _groundY(tx, ty) + 0.35, z);
      _dummy.rotation.set(0, 0, 0);
      _dummy.scale.set(1, 1, 1);
      _dummy.updateMatrix();
      waterMesh.setMatrixAt(wi, _dummy.matrix);
      const wN = hasW(tx, ty - 1);
      const wE = hasW(tx + 1, ty);
      const wS = hasW(tx, ty + 1);
      const wW = hasW(tx - 1, ty);
      const neD = hasW(tx + 1, ty - 1);
      const nwD = hasW(tx - 1, ty - 1);
      const seD = hasW(tx + 1, ty + 1);
      const swD = hasW(tx - 1, ty + 1);
      // Max corner radius in IQ sdRoundBox (shader uses half-extents b=vec2(1) in p-space). Rc=1
      // with all four corners active yields a circle for an isolated tile; outer convex pond corners
      // use full quarter-arcs. Diagonals zero r along straight shores / interior cardinals.
      // Concave inner vertices (grass on diagonal): r=0 on sdRoundBox + shader subtracts a quarter-arc
      // (disk center on bisector into grass). Extra cardinal/diagonal rules
      // avoid V-notches along straight shores.
      const Rc = 1.0;
      const rNE =
        (wN && wE) ||
        (!wN && wE && !neD) ||
        (wN && !wE && !neD) ||
        (wN && !wE && neD) ||
        (!wN && wE && neD)
          ? 0
          : Rc;
      const rSE =
        (wS && wE) ||
        (!wS && wE && !seD) ||
        (wS && !wE && !seD) ||
        (wS && !wE && seD) ||
        (!wS && wE && seD)
          ? 0
          : Rc;
      const rNW =
        (wN && wW) ||
        (!wN && wW && !nwD) ||
        (wN && !wW && !nwD) ||
        (wN && !wW && nwD) ||
        (!wN && wW && nwD)
          ? 0
          : Rc;
      const rSW =
        (wS && wW) ||
        (!wS && wW && !swD) ||
        (wS && !wW && !swD) ||
        (wS && !wW && swD) ||
        (!wS && wW && swD)
          ? 0
          : Rc;
      const o = wi * 4;
      // sdRoundBox vec4 = (NE, SE, NW, SW) — pairs (r.xy|r.zw) = east|west halves for IQ selection
      waterRArr[o] = rNE;
      waterRArr[o + 1] = rSE;
      waterRArr[o + 2] = rNW;
      waterRArr[o + 3] = rSW;
      waterFilletArr[o] = wN && wE && !neD ? 1 : 0;
      waterFilletArr[o + 1] = wS && wE && !seD ? 1 : 0;
      waterFilletArr[o + 2] = wN && wW && !nwD ? 1 : 0;
      waterFilletArr[o + 3] = wS && wW && !swD ? 1 : 0;
      wi += 1;
    };
    const bridgeSet = new Set((s.bridge_tiles || []).map((b) => `${b.x},${b.y}`));
    const pushR = (tx, ty) => {
      if (ri >= MAX_ROAD) return;
      if (bridgeSet.has(`${tx},${ty}`)) return;
      const { x, z } = _worldXZ(tx, ty);
      _dummy.position.set(x, _groundY(tx, ty) + 0.62, z);
      _dummy.rotation.set(-Math.PI / 2, 0, 0);
      _dummy.scale.set(1, 1, 1);
      _dummy.updateMatrix();
      roadMesh.setMatrixAt(ri++, _dummy.matrix);
    };
    for (const w of s.water_tiles || []) {
      if (w.x < sx - 1 || w.x > ex + 1 || w.y < sy - 1 || w.y > ey + 1) continue;
      pushW(w.x, w.y);
    }
    for (const r of s.roads || []) {
      if (r.x < sx - 1 || r.x > ex + 1 || r.y < sy - 1 || r.y > ey + 1) continue;
      pushR(r.x, r.y);
    }
    waterMesh.count = wi;
    roadMesh.count = ri;
    waterMesh.instanceMatrix.needsUpdate = true;
    waterRAttr.needsUpdate = true;
    waterFilletAttr.needsUpdate = true;
    roadMesh.instanceMatrix.needsUpdate = true;
  }

  function _soilFurrows(sx, sy, ex, ey) {
    const crops = s.crops || [];
    const atCrop = (x, y) => crops.some((c) => c.x === x && c.y === y);
    const pts = [];
    for (const st of s.soil_tiles || []) {
      if (!st.tilled || atCrop(st.x, st.y)) continue;
      if (st.x < sx - 1 || st.x > ex + 1 || st.y < sy - 1 || st.y > ey + 1) continue;
      const ox = st.x * T;
      const oz = st.y * T;
      const gy = _groundY(st.x, st.y) + 1.2;
      for (let i = 0; i < 4; i++) {
        const x0 = ox + 5 + i * 7;
        const z0 = oz + 5;
        const x1 = ox + 4 + i * 7;
        const z1 = oz + T - 5;
        pts.push(new THREE.Vector3(x0, gy, z0), new THREE.Vector3(x1, gy, z1));
      }
    }
    if (!pts.length) return;
    const geom = new THREE.BufferGeometry().setFromPoints(pts);
    const mat = new THREE.LineBasicMaterial({ color: 0x5f4128, transparent: true, opacity: 0.35 });
    const lines = new THREE.LineSegments(geom, mat);
    dynamicRoot.add(lines);
  }

  function _bridges(sx, sy, ex, ey) {
    for (const b of s.bridge_tiles || []) {
      if (b.x < sx - 1 || b.x > ex + 1 || b.y < sy - 1 || b.y > ey + 1) continue;
      const { x, z } = _worldXZ(b.x, b.y);
      const g = new THREE.BoxGeometry(T - 6, 3, T - 8);
      const m = new THREE.MeshLambertMaterial({ color: 0x6e5234 });
      const mesh = new THREE.Mesh(g, m);
      mesh.position.set(x, _groundY(b.x, b.y) + 2.5, z);
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      dynamicRoot.add(mesh);
    }
  }

  function _towns() {
    for (const town of s.towns || []) {
      const poly = town.boundary;
      if (!poly || poly.length < 3) continue;
      const col = TOWN_HEX[town.id % TOWN_HEX.length];
      const shape = new THREE.Shape();
      const p0 = _worldXZ(poly[0].x, poly[0].y);
      shape.moveTo(p0.x, p0.z);
      for (let i = 1; i < poly.length; i++) {
        const p = _worldXZ(poly[i].x, poly[i].y);
        shape.lineTo(p.x, p.z);
      }
      shape.closePath();
      const geom = new THREE.ShapeGeometry(shape);
      const mat = new THREE.MeshBasicMaterial({
        color: col,
        transparent: true,
        opacity: s.currentTownId === town.id ? 0.09 : 0.045,
        depthWrite: false,
        side: THREE.DoubleSide,
      });
      const mesh = new THREE.Mesh(geom, mat);
      mesh.rotation.x = -Math.PI / 2;
      mesh.position.y = _groundY(town.center_x, town.center_y) + 0.4;
      overlayRoot.add(mesh);
      const edges = new THREE.LineLoop(
        new THREE.BufferGeometry().setFromPoints(
          poly.map((q) => {
            const w = _worldXZ(q.x, q.y);
            return new THREE.Vector3(w.x, _groundY(q.x, q.y) + 1.2, w.z);
          }),
        ),
        new THREE.LineBasicMaterial({
          color: col,
          transparent: true,
          opacity: s.currentTownId === town.id ? 0.55 : 0.22,
        }),
      );
      overlayRoot.add(edges);
      const cnx = town.center_x * T + T / 2;
      const cny = town.center_y * T + T / 2;
      _spriteText(town.name, cnx, _groundY(town.center_x, town.center_y) + 40, cny, col, true);
    }
  }

  function _spriteText(text, x, y, z, colorHex, bold) {
    const cvs = document.createElement('canvas');
    const pad = 8;
    cvs.width = 512;
    cvs.height = 128;
    const c2 = cvs.getContext('2d');
    c2.font = (bold ? 'bold ' : '') + '36px monospace';
    c2.textAlign = 'center';
    c2.textBaseline = 'middle';
    c2.fillStyle = 'rgba(0,0,0,0.65)';
    c2.fillText(text, 258, 66);
    c2.fillStyle = `#${new THREE.Color(colorHex).getHexString()}`;
    c2.fillText(text, 256, 64);
    const tex = new THREE.CanvasTexture(cvs);
    tex.colorSpace = THREE.SRGBColorSpace;
    const mat = new THREE.SpriteMaterial({ map: tex, transparent: true });
    const spr = new THREE.Sprite(mat);
    spr.position.set(x, y, z);
    spr.scale.set(220, 55, 1);
    overlayRoot.add(spr);
  }

  function _parcels(sx, sy, ex, ey) {
    const px = s.player ? s.player.x : 0;
    const py = s.player ? s.player.y : 0;
    for (const p of s.world_parcels || []) {
      if (p.x + p.w < sx - 2 || p.x > ex + 2 || p.y + p.h < sy - 2 || p.y > ey + 2) continue;
      const onThisParcel = px >= p.x && px < p.x + p.w && py >= p.y && py < p.y + p.h;
      const previewThis = s.parcelPreview === p.id;
      if (!onThisParcel && !previewThis) continue;

      const ox = p.x * T;
      const oy = p.y * T;
      const pw = p.w * T;
      const ph = p.h * T;
      const cx = ox + pw / 2;
      const cz = oy + ph / 2;
      const isMine = s.player && p.owner_id === s.player.id;
      const isPreview = s.parcelPreview === p.id;
      const isCurrent = px >= p.x && px < p.x + p.w && py >= p.y && py < p.y + p.h;
      let color = 0x888888;
      let op = 0.06;
      if (isPreview) { color = 0xffdc32; op = 0.2; }
      else if (isMine) { color = 0x64c864; op = 0.1; }
      else if (isCurrent && !p.owner_id) { color = 0xffffcc; op = 0.08; }
      const tcx = Math.floor(p.x + p.w / 2);
      const tcy = Math.floor(p.y + p.h / 2);
      const gBase = _groundY(tcx, tcy);
      const g = new THREE.PlaneGeometry(pw, ph);
      g.rotateX(-Math.PI / 2);
      const m = new THREE.MeshBasicMaterial({
        color,
        transparent: true,
        opacity: op,
        depthWrite: false,
      });
      const mesh = new THREE.Mesh(g, m);
      mesh.position.set(cx, gBase + 0.55, cz);
      overlayRoot.add(mesh);
      const h = gBase + 0.5;
      const line = new THREE.LineSegments(
        new THREE.EdgesGeometry(new THREE.PlaneGeometry(pw - 1, ph - 1)),
        new THREE.LineBasicMaterial({
          color,
          transparent: true,
          opacity: isPreview ? 0.85 : isMine ? 0.45 : 0.25,
        }),
      );
      line.rotation.x = -Math.PI / 2;
      line.position.set(cx, h, cz);
      overlayRoot.add(line);
      if (isPreview) {
        _spriteText(`${p.price}c`, cx, gBase + 28, cz, 0xffdc32, true);
      } else if (isMine && pw >= 32) {
        _spriteText(p.owner_name || '', cx, gBase + 22, cz, 0x88ff88, false);
      } else if (p.owner_id && isCurrent && pw >= 32) {
        _spriteText(p.owner_name || '?', cx, gBase + 22, cz, 0xffaa88, false);
      }
    }
  }

  function _ensureOnDynamicRoot(g) {
    if (g.parent !== dynamicRoot) dynamicRoot.add(g);
  }

  function _ensureNodeMesh(i) {
    while (nodePool.length <= i) {
      const g = new THREE.Group();
      nodePool.push(g);
      dynamicRoot.add(g);
    }
    const g = nodePool[i];
    _ensureOnDynamicRoot(g);
    return g;
  }

  function _hideNodePool() {
    for (let i = nodePoolUsed; i < nodePool.length; i++) {
      nodePool[i].visible = false;
    }
  }

  function _structureMesh(type) {
    const g = new THREE.Group();
    let body;
    switch (type) {
      case 'manure':
        body = new THREE.Mesh(
          new THREE.BoxGeometry(T - 8, 18, T - 8),
          new THREE.MeshLambertMaterial({ color: 0x6a5040 }),
        );
        body.position.y = 9;
        break;
      case 'gravel':
        body = new THREE.Mesh(
          new THREE.ConeGeometry(14, 22, 6),
          new THREE.MeshLambertMaterial({ color: 0x888888 }),
        );
        body.position.y = 10;
        break;
      case 'compost':
        body = new THREE.Mesh(
          new THREE.CylinderGeometry(12, 14, 16, 8),
          new THREE.MeshLambertMaterial({ color: 0x3a3020 }),
        );
        body.position.y = 9;
        break;
      case 'topsoil':
        body = new THREE.Mesh(
          new THREE.CylinderGeometry(13, 13, 10, 10),
          new THREE.MeshLambertMaterial({ color: 0x5a4838 }),
        );
        body.position.y = 6;
        break;
      default:
        body = new THREE.Mesh(
          new THREE.BoxGeometry(T - 6, 20, T - 6),
          new THREE.MeshLambertMaterial({ color: 0x5a5a4a }),
        );
        body.position.y = 10;
    }
    body.castShadow = true;
    g.add(body);
    return g;
  }

  function _wildMesh(node) {
    const g = new THREE.Group();
    const { x, z } = _worldXZ(node.x, node.y);
    g.userData.baseX = x;
    g.userData.baseZ = z;
    switch (node.type) {
      case 'wood': {
        const v = ((node.tree_variant == null ? 0 : node.tree_variant) | 0) & 15;
        const trunk = new THREE.Mesh(
          new THREE.CylinderGeometry(3, 4, 14, 6),
          new THREE.MeshLambertMaterial({ color: 0x4a3220 }),
        );
        trunk.position.y = 8;
        trunk.castShadow = true;
        g.add(trunk);
        const crown = v >= 8
          ? new THREE.Mesh(
            new THREE.ConeGeometry(14, 22, 7),
            new THREE.MeshLambertMaterial({ color: 0x1d5020 }),
          )
          : new THREE.Mesh(
            new THREE.SphereGeometry(12, 8, 6),
            new THREE.MeshLambertMaterial({ color: 0x2f7a32 }),
          );
        crown.position.y = 24;
        crown.castShadow = true;
        g.add(crown);
        break;
      }
      case 'stone': {
        const m = new THREE.Mesh(
          new THREE.DodecahedronGeometry(11, 0),
          new THREE.MeshLambertMaterial({ color: 0x8a8a90 }),
        );
        m.position.y = 10;
        m.castShadow = true;
        g.add(m);
        break;
      }
      case 'gravel': {
        const m = new THREE.Mesh(
          new THREE.IcosahedronGeometry(10, 0),
          new THREE.MeshLambertMaterial({ color: 0x909088 }),
        );
        m.position.y = 9;
        m.castShadow = true;
        g.add(m);
        break;
      }
      case 'clay': {
        const m = new THREE.Mesh(
          new THREE.BoxGeometry(16, 10, 14),
          new THREE.MeshLambertMaterial({ color: 0xa07058 }),
        );
        m.position.y = 7;
        m.castShadow = true;
        g.add(m);
        break;
      }
      case 'dirt':
      case 'topsoil': {
        const m = new THREE.Mesh(
          new THREE.CylinderGeometry(11, 12, 8, 8),
          new THREE.MeshLambertMaterial({ color: node.type === 'dirt' ? 0x6a5040 : 0x5a4838 }),
        );
        m.position.y = 5;
        m.castShadow = true;
        g.add(m);
        break;
      }
      default: {
        const m = new THREE.Mesh(
          new THREE.BoxGeometry(12, 10, 12),
          new THREE.MeshLambertMaterial({ color: 0x555555 }),
        );
        m.position.y = 6;
        m.castShadow = true;
        g.add(m);
        break;
      }
    }
    return g;
  }

  function _marketMesh(dark, light) {
    const g = new THREE.Group();
    const stall = new THREE.Mesh(
      new THREE.BoxGeometry(T - 4, 20, T - 6),
      new THREE.MeshLambertMaterial({ color: dark }),
    );
    stall.position.y = 11;
    stall.castShadow = true;
    g.add(stall);
    const awning = new THREE.Mesh(
      new THREE.BoxGeometry(T + 2, 3, T),
      new THREE.MeshLambertMaterial({ color: light }),
    );
    awning.position.set(0, 22, 0);
    g.add(awning);
    return g;
  }

  function _siloMesh(node) {
    const g = new THREE.Group();
    const cyl = new THREE.Mesh(
      new THREE.CylinderGeometry(12, 12, 26, 12),
      new THREE.MeshLambertMaterial({ color: 0x9aa8b8 }),
    );
    cyl.position.y = 16;
    cyl.castShadow = true;
    g.add(cyl);
    const cap = new THREE.Mesh(
      new THREE.CylinderGeometry(12, 10, 4, 12),
      new THREE.MeshLambertMaterial({ color: 0xb8c0d0 }),
    );
    cap.position.y = 31;
    g.add(cap);
    return g;
  }

  function _townHallMesh() {
    const g = new THREE.Group();
    const base = new THREE.Mesh(
      new THREE.BoxGeometry(T - 2, 24, T - 2),
      new THREE.MeshLambertMaterial({ color: 0x5a4830 }),
    );
    base.position.y = 13;
    base.castShadow = true;
    g.add(base);
    const roof = new THREE.Mesh(
      new THREE.ConeGeometry(20, 12, 4),
      new THREE.MeshLambertMaterial({ color: 0x8a2020 }),
    );
    roof.position.y = 32;
    roof.rotation.y = Math.PI / 4;
    g.add(roof);
    return g;
  }

  function _constructionMesh() {
    const g = new THREE.Group();
    const slab = new THREE.Mesh(
      new THREE.BoxGeometry(T - 6, 4, T - 8),
      new THREE.MeshLambertMaterial({ color: 0x8a7860 }),
    );
    slab.position.y = 3;
    g.add(slab);
    const frame = new THREE.Mesh(
      new THREE.BoxGeometry(T - 10, 18, T - 12),
      new THREE.MeshLambertMaterial({ color: 0xc9b090 }),
    );
    frame.position.y = 14;
    frame.castShadow = true;
    g.add(frame);
    return g;
  }

  function _nodeObjectFor(node) {
    if (node.construction_active) return _constructionMesh();
    if (node.is_market) return _marketMesh(0x602060, 0xa040a0);
    if (node.is_town_hall) return _townHallMesh();
    if (node.is_structure) {
      if (node.is_silo) return _siloMesh(node);
      return _structureMesh(node.type);
    }
    return _wildMesh(node);
  }

  function _fillNodeGroup(grp, node) {
    while (grp.children.length) {
      const ch = grp.children[0];
      grp.remove(ch);
    }
    const built = _nodeObjectFor(node);
    while (built.children.length) grp.add(built.children[0]);
    if (built instanceof THREE.Mesh) grp.add(built);
  }

  function _nodes(sx, sy, ex, ey) {
    nodePoolUsed = 0;
    for (const node of s.nodes || []) {
      if (node.x < sx - 2 || node.x > ex + 2 || node.y < sy - 2 || node.y > ey + 2) continue;
      const grp = _ensureNodeMesh(nodePoolUsed++);
      _fillNodeGroup(grp, node);
      const { x, z } = _worldXZ(node.x, node.y);
      const gy = _groundY(node.x, node.y);
      grp.position.set(x, gy, z);
      grp.visible = true;
      if (node.owner_name && (node.is_structure || node.is_market)) {
        _spriteText(node.owner_name, x, gy + 48, z, 0xccffaa, false);
      }
    }
    _hideNodePool();
  }

  function _npcMarkers(sx, sy, ex, ey) {
    for (const m of s.npc_markets || []) {
      if (m.x < sx - 2 || m.x > ex + 2 || m.y < sy - 2 || m.y > ey + 2) continue;
      const { x, z } = _worldXZ(m.x, m.y);
      const my = _groundY(m.x, m.y);
      const grp = _marketMesh(0xb89010, 0xf0d050);
      grp.position.set(x, my, z);
      dynamicRoot.add(grp);
      _spriteText('Market', x, my + 52, z, 0xffe080, true);
    }
    for (const shop of s.npc_shops || []) {
      if (shop.x < sx - 2 || shop.x > ex + 2 || shop.y < sy - 2 || shop.y > ey + 2) continue;
      const { x, z } = _worldXZ(shop.x, shop.y);
      const shopGy = _groundY(shop.x, shop.y);
      let grp;
      if (shop.label.includes('Seed')) grp = _marketMesh(0x206020, 0x40a040);
      else if (shop.label.includes('General')) grp = _marketMesh(0x404080, 0x6060a0);
      else grp = _marketMesh(0x804040, 0xa06060);
      grp.position.set(x, shopGy, z);
      dynamicRoot.add(grp);
      const shortName = shop.label.replace(' Shop', '').replace(' Store', '');
      _spriteText(shortName, x, shopGy + 48, z, 0xccccff, false);
    }
  }

  function _ensurePile(i) {
    while (pilePool.length <= i) {
      const g = new THREE.Group();
      pilePool.push(g);
      dynamicRoot.add(g);
    }
    const g = pilePool[i];
    _ensureOnDynamicRoot(g);
    return g;
  }

  function _piles(sx, sy, ex, ey) {
    pilePoolUsed = 0;
    const colors = {
      wood: 0x4a7a32, stone: 0x888890, gravel: 0xa0a098, clay: 0xb08068,
      dirt: 0x6a5040, wheat: 0xd8c060, fertilizer: 0xe8e8f0, compost: 0x3a3020,
      manure: 0x4a3828, topsoil: 0x5a4838,
    };
    for (const pile of s.piles || []) {
      if (pile.x < sx - 2 || pile.x > ex + 2 || pile.y < sy - 2 || pile.y > ey + 2) continue;
      const grp = _ensurePile(pilePoolUsed++);
      while (grp.children.length) grp.remove(grp.children[0]);
      const { x, z } = _worldXZ(pile.x, pile.y);
      const pileGy = _groundY(pile.x, pile.y);
      const col = colors[pile.resource_type] || 0x888888;
      const n = Math.min(5, 2 + Math.floor((pile.amount || 0) / 20));
      for (let i = 0; i < n; i++) {
        const siz = 5 + (i % 3) * 2;
        const m = new THREE.Mesh(
          new THREE.SphereGeometry(siz, 6, 5),
          new THREE.MeshLambertMaterial({ color: col }),
        );
        m.position.set((i % 3 - 1) * 6, 4 + i * 3, (i % 2) * 4);
        m.castShadow = true;
        grp.add(m);
      }
      grp.position.set(x, pileGy, z);
      grp.visible = true;
      if (pile.sell_price != null) {
        _spriteText(`${pile.sell_price}c`, x, pileGy + 28 + n * 3, z, 0xf5c842, true);
      }
    }
    for (let i = pilePoolUsed; i < pilePool.length; i++) pilePool[i].visible = false;
  }

  function _ensureCrop(i) {
    while (cropPool.length <= i) {
      const g = new THREE.Group();
      cropPool.push(g);
      dynamicRoot.add(g);
    }
    const g = cropPool[i];
    _ensureOnDynamicRoot(g);
    return g;
  }

  function _crops(sx, sy, ex, ey) {
    cropPoolUsed = 0;
    for (const crop of s.crops || []) {
      if (crop.x < sx - 2 || crop.x > ex + 2 || crop.y < sy - 2 || crop.y > ey + 2) continue;
      const grp = _ensureCrop(cropPoolUsed++);
      while (grp.children.length) grp.remove(grp.children[0]);
      const { x, z } = _worldXZ(crop.x, crop.y);
      const cy = _groundY(crop.x, crop.y);
      if (crop.winter_dead) {
        for (let i = 0; i < 3; i++) {
          const m = new THREE.Mesh(
            new THREE.CylinderGeometry(1, 2, 10, 5),
            new THREE.MeshLambertMaterial({ color: 0x5a5048 }),
          );
          m.position.set(-6 + i * 6, 6, -4 + (i % 2) * 4);
          grp.add(m);
        }
      } else if (crop.ready) {
        const m = new THREE.Mesh(
          new THREE.ConeGeometry(10, 24, 8),
          new THREE.MeshLambertMaterial({ color: 0xc8b030 }),
        );
        m.position.y = 12;
        grp.add(m);
      } else {
        const col = crop.fertilized ? 0x40a020 : 0x709020;
        for (let i = 0; i < 5; i++) {
          const blade = new THREE.Mesh(
            new THREE.ConeGeometry(3, 14, 4),
            new THREE.MeshLambertMaterial({ color: col }),
          );
          blade.position.set(-8 + i * 4, 8, (i % 2) * 2);
          grp.add(blade);
        }
      }
      grp.position.set(x, cy, z);
      grp.visible = true;
    }
    for (let i = cropPoolUsed; i < cropPool.length; i++) cropPool[i].visible = false;
  }

  function _facingYaw(f) {
    if (f === 'left') return Math.PI / 2;
    if (f === 'right') return -Math.PI / 2;
    if (f === 'up') return Math.PI;
    return 0;
  }

  /** Server angle (east=0, south=π/2) → Y rotation; discrete facing as fallback. */
  function _yawFromFacingOrAngle(facingOrAngle) {
    if (typeof facingOrAngle === 'number' && Number.isFinite(facingOrAngle)) {
      return -facingOrAngle + Math.PI / 2;
    }
    return _facingYaw(facingOrAngle || 'down');
  }

  /**
   * Classic single-wheel barrow (+Z forward): two straight wood rails in a V (narrow at axle, wide at
   * handles), open bucket on top, metal legs, wheel + axle — minimal parts.
   */
  function _wheelbarrow3d(grp, colorHex, flatTire, loadFrac, facingOrAngle, label) {
    const yaw = _yawFromFacingOrAngle(facingOrAngle);
    const yawKey = (Math.round(yaw * 48) / 48).toFixed(4);
    const loadKey = (Math.round(loadFrac * 24) / 24).toFixed(3);
    const cacheKey = `${yawKey}|${flatTire ? 1 : 0}|${loadKey}|${colorHex}`;
    if (grp.userData._wbCacheKey === cacheKey) {
      grp.rotation.y = yaw;
      if (label && grp.userData.wx != null) {
        const gyy = grp.userData.gy != null ? grp.userData.gy : 0;
        _spriteText(label, grp.userData.wx, gyy + 44, grp.userData.wz, 0xffffff, true);
      }
      return;
    }
    grp.userData._wbCacheKey = cacheKey;
    while (grp.children.length) {
      const ch = grp.children[0];
      ch.traverse((o) => {
        if (o.geometry) o.geometry.dispose();
        if (o.material) {
          const m = o.material;
          if (Array.isArray(m)) m.forEach((x) => x.dispose());
          else m.dispose();
        }
      });
      grp.remove(ch);
    }
    const paint = new THREE.Color(colorHex);
    const wood = new THREE.MeshLambertMaterial({ color: 0x5c4330 });
    const woodEnd = new THREE.MeshLambertMaterial({ color: 0x6b5240 });
    const steel = new THREE.MeshLambertMaterial({ color: paint });
    const steelDark = new THREE.MeshLambertMaterial({ color: paint.clone().multiplyScalar(0.75) });
    const steelRim = new THREE.MeshLambertMaterial({ color: paint.clone().multiplyScalar(0.92) });
    const rubber = new THREE.MeshLambertMaterial({ color: flatTire ? 0x6a2028 : 0x101010 });
    const rimMetal = new THREE.MeshLambertMaterial({ color: 0x4a4d52 });

    const wheelR = flatTire ? 6.2 : 8.0;
    const wheelW = 3.2;
    // Rail tips at z=fz — wheel centered in the V; axle only spans rail spacing (matches fz below).
    const axleZ = 12.95;
    const axleY = wheelR;
    const axleLen = 10.2;

    const tire = new THREE.Mesh(new THREE.CylinderGeometry(wheelR, wheelR, wheelW, 28), rubber);
    tire.rotation.z = Math.PI / 2;
    tire.position.set(0, axleY, axleZ);
    tire.castShadow = true;
    if (flatTire) tire.scale.set(1, 0.7, 0.7);
    grp.add(tire);

    const hub = new THREE.Mesh(
      new THREE.CylinderGeometry(wheelR * 0.26, wheelR * 0.26, wheelW + 0.35, 16),
      rimMetal,
    );
    hub.rotation.z = Math.PI / 2;
    hub.position.set(0, axleY, axleZ);
    grp.add(hub);

    const axle = new THREE.Mesh(new THREE.CylinderGeometry(0.85, 0.85, axleLen, 10), rimMetal);
    axle.rotation.z = Math.PI / 2;
    axle.position.set(0, axleY, axleZ);
    axle.castShadow = true;
    grp.add(axle);

    const nose = new THREE.Mesh(new THREE.BoxGeometry(10.5, 1.4, 2.2), rimMetal);
    nose.position.set(0, axleY - 1.2, 12.35);
    nose.castShadow = true;
    grp.add(nose);

    const railW = 2.5;
    const railH = 2.9;
    const railY = 10.5;
    const fz = 12.5;
    const bz = -30;
    for (const sx of [-1, 1]) {
      const fx = sx * 4.5;
      const bx = sx * 13.0;
      const dx = bx - fx;
      const dz = bz - fz;
      const len = Math.hypot(dx, dz);
      const railYaw = Math.atan2(dx, dz);
      const rail = new THREE.Mesh(new THREE.BoxGeometry(railW, railH, len), wood);
      rail.position.set((fx + bx) / 2, railY, (fz + bz) / 2);
      rail.rotation.y = railYaw;
      rail.castShadow = true;
      grp.add(rail);
      const cap = new THREE.Mesh(new THREE.SphereGeometry(1.25, 10, 10), woodEnd);
      cap.position.set(bx, railY + 0.15, bz);
      cap.castShadow = true;
      grp.add(cap);
    }

    const tz = -4;
    const tubD = 24;
    const tubW = 18;
    const wallH = 7.5;
    const wallT = 1.5;

    const floor = new THREE.Mesh(new THREE.BoxGeometry(tubW - 0.5, 1.4, tubD), steelDark);
    floor.rotation.x = 0.12;
    floor.position.set(0, 14.0, tz);
    floor.castShadow = true;
    grp.add(floor);

    for (const sx of [-1, 1]) {
      const side = new THREE.Mesh(new THREE.BoxGeometry(wallT, wallH, tubD - 1), steel);
      side.position.set(sx * (tubW * 0.5 - wallT * 0.4), 18.0, tz);
      side.castShadow = true;
      grp.add(side);
    }

    const back = new THREE.Mesh(new THREE.BoxGeometry(tubW + 1, wallH + 0.8, wallT), steelDark);
    back.position.set(0, 18.2, tz - tubD * 0.5 + wallT * 0.45);
    back.castShadow = true;
    grp.add(back);

    const lip = new THREE.Mesh(new THREE.BoxGeometry(tubW + 0.5, 2.8, 8), steelRim);
    lip.position.set(0, 18.5, tz + tubD * 0.5 - 3.5);
    lip.rotation.x = -0.38;
    lip.castShadow = true;
    grp.add(lip);

    for (const sx of [-1, 1]) {
      const leg = new THREE.Mesh(new THREE.BoxGeometry(2.2, 9, 1.4), rimMetal);
      leg.position.set(sx * 7.5, 4.5, -12);
      leg.rotation.z = sx * 0.08;
      leg.castShadow = true;
      grp.add(leg);
      const foot = new THREE.Mesh(new THREE.BoxGeometry(3.5, 1.2, 3.2), rimMetal);
      foot.position.set(sx * 7.8, 0.65, -12);
      foot.castShadow = true;
      grp.add(foot);
    }
    const legBrace = new THREE.Mesh(new THREE.BoxGeometry(14, 0.9, 1.8), rimMetal);
    legBrace.position.set(0, 2.2, -12);
    grp.add(legBrace);

    if (loadFrac > 0.02) {
      const load = new THREE.Mesh(
        new THREE.BoxGeometry(tubW - 4, 6 * loadFrac, tubD - 7),
        new THREE.MeshLambertMaterial({ color: 0x88d050, transparent: true, opacity: 0.88 }),
      );
      load.position.set(0, 15.5 + 2.8 * loadFrac, tz - 1);
      grp.add(load);
    }

    grp.rotation.y = yaw;
    if (label && grp.userData.wx != null) {
      const gyy = grp.userData.gy != null ? grp.userData.gy : 0;
      _spriteText(label, grp.userData.wx, gyy + 44, grp.userData.wz, 0xffffff, true);
    }
  }

  function _ensureWb(i) {
    while (wbPool.length <= i) {
      const g = new THREE.Group();
      wbPool.push(g);
      dynamicRoot.add(g);
    }
    const g = wbPool[i];
    _ensureOnDynamicRoot(g);
    return g;
  }

  function _players(sx, sy, ex, ey, smoothX, smoothY) {
    wbPoolUsed = 0;
    for (const p of s.players || []) {
      if (!p || p.id == null || !s.player || p.id === s.player.id) continue;
      if (p.x < sx - 2 || p.x > ex + 2 || p.y < sy - 2 || p.y > ey + 2) continue;
      const face = s._otherFacing[p.id] || 'down';
      const grp = _ensureWb(wbPoolUsed++);
      const { x, z } = _worldXZ(p.x, p.y);
      const gy = _groundY(p.x, p.y);
      grp.userData.gy = gy;
      grp.position.set(x, gy, z);
      grp.userData.wx = x;
      grp.userData.wz = z;
      const orient = p.angle != null && Number.isFinite(p.angle) ? p.angle : face;
      _wheelbarrow3d(grp, '#6ab0e8', p.flat_tire, 0, orient, p.username || '');
      grp.visible = true;
    }
    if (s.player) {
      const plx = smoothX != null ? smoothX : s.player.x;
      const ply = smoothY != null ? smoothY : s.player.y;
      const bucket = s.player.bucket || {};
      const total = Object.values(bucket).reduce((a, b) => a + b, 0);
      const cap = s.player.bucket_cap_effective != null ? s.player.bucket_cap_effective : (s.player.bucket_cap || 10);
      const face = s.facing || 'down';
      const grp = _ensureWb(wbPoolUsed++);
      const { x, z } = _worldXZ(plx, ply);
      const gy = _groundY(plx, ply);
      grp.userData.gy = gy;
      grp.position.set(x, gy, z);
      grp.userData.wx = x;
      grp.userData.wz = z;
      const orient = s.player.angle != null && Number.isFinite(s.player.angle) ? s.player.angle : face;
      _wheelbarrow3d(grp, '#f5c842', s.player.flat_tire, Math.min(1, total / cap), orient, null);
      grp.visible = true;
    }
    for (let i = wbPoolUsed; i < wbPool.length; i++) wbPool[i].visible = false;
  }

  function _clearOverlay() {
    while (overlayRoot.children.length) {
      const ch = overlayRoot.children[0];
      if (ch.material) {
        if (ch.material.map) ch.material.map.dispose();
        ch.material.dispose();
      }
      if (ch.geometry) ch.geometry.dispose();
      overlayRoot.remove(ch);
    }
  }

  function draw() {
    if (!s.player || typeof THREE === 'undefined') return;
    if (!renderer || !scene || !camera) return;
    if (!_dummy || !_c) return;
    const W = Math.max(1, canvas.width | 0);
    const H = Math.max(1, canvas.height | 0);
    if (!Number.isFinite(s.player.x) || !Number.isFinite(s.player.y)) return;
    _vpW = W;
    _vpH = H;
    const px = s.player.x;
    const py = s.player.y;
    if (!Number.isFinite(s._renderSmoothX)) {
      s._renderSmoothX = px;
      s._renderSmoothY = py;
    }
    if (Math.hypot(px - s._renderSmoothX, py - s._renderSmoothY) > 10) {
      s._renderSmoothX = px;
      s._renderSmoothY = py;
    } else {
      const sk = 0.38;
      s._renderSmoothX += (px - s._renderSmoothX) * sk;
      s._renderSmoothY += (py - s._renderSmoothY) * sk;
    }
    const rx = s._renderSmoothX;
    const ry = s._renderSmoothY;
    _camX = rx * T - W / 2 + T / 2;
    _camY = ry * T - H / 2 + T / 2;

    try {
    _applySeasonAtmosphere();
    const sunX = rx * T + T / 2;
    const sunZ = ry * T + T / 2;
    sun.position.set(sunX + 320, 1250, sunZ + 220);

    while (dynamicRoot.children.length) {
      const ch = dynamicRoot.children[0];
      ch.traverse((o) => {
        if (o.geometry) o.geometry.dispose();
        if (o.material) {
          const m = o.material;
          if (Array.isArray(m)) m.forEach((x) => x.dispose());
          else m.dispose();
        }
      });
      dynamicRoot.remove(ch);
    }

    _clearOverlay();

    const wx = s.world ? s.world.w : 1000;
    const wy = s.world ? s.world.h : 1000;

    _updateCamera(rx, ry);
    let sx;
    let sy;
    let ex;
    let ey;
    const vr = _visibleTileRange(wx, wy, rx, ry);
    if (vr) {
      sx = vr.sx;
      sy = vr.sy;
      ex = vr.ex;
      ey = vr.ey;
    } else {
      const span = Math.min(52, Math.ceil(Math.max(W, H) / T) + 8);
      sx = Math.max(0, Math.floor(rx - span));
      sy = Math.max(0, Math.floor(ry - span));
      ex = Math.min(wx - 1, Math.ceil(rx + span));
      ey = Math.min(wy - 1, Math.ceil(ry + span));
    }
    const tr = _expandTileRangeForGroundLayers(sx, sy, ex, ey, wx, wy, rx, ry);
    sx = tr.sx;
    sy = tr.sy;
    ex = tr.ex;
    ey = tr.ey;

    const gwy = _groundY(rx, ry);
    horizonGrass.position.set(rx * T + T / 2, gwy - 0.35, ry * T + T / 2);
    const hzRgb = _fieldGrassRgb(Math.floor(rx), Math.floor(ry));
    horizonGrass.material.color.setRGB(hzRgb.r, hzRgb.g, hzRgb.b);

    const perfNow = typeof performance !== 'undefined' ? performance.now() : Date.now();
    const grassAttr = grassMesh.geometry && grassMesh.geometry.getAttribute('position');
    const grassStale = !grassAttr || !grassAttr.count;
    if (grassStale || perfNow - _lastGrassBuildMs >= GRASS_REBUILD_MS) {
      _lastGrassBuildMs = perfNow;
      _setGrassTiles(rx, ry, wx, wy, hzRgb.r, hzRgb.g, hzRgb.b);
    }
    _waterAndRoadsInView(sx, sy, ex, ey);
    _soilFurrows(sx, sy, ex, ey);
    _bridges(sx, sy, ex, ey);
    _towns();
    _parcels(sx, sy, ex, ey);
    _nodes(sx, sy, ex, ey);
    _npcMarkers(sx, sy, ex, ey);
    _piles(sx, sy, ex, ey);
    _crops(sx, sy, ex, ey);
    _players(sx, sy, ex, ey, rx, ry);

    renderer.render(scene, camera);
    } catch (err) {
      console.error('Wheelbarrow renderer.draw:', err);
    }
  }

  return { init, draw, getCameraMoveBasis, getCameraFacingAngle };
})();
