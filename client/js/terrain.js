/**
 * Rolling elevation (shared server formula in server/game/terrain_elevation.py).
 * Hills — height is smooth across tile integer coords.
 *
 * Tiles are T=32 world units wide; the old scale (×12) gave ~0.5–1 ΔY per tile
 * (~1–2° slope), which read as flat. WORLD_Y_SCALE is chosen so adjacent-tile
 * steps are a few world units (visibly terraced grass planes).
 */
const Terrain = (() => {
  const DEFAULT_W = 1000;
  const DEFAULT_H = 1000;
  /** Matches server/game/terrain_elevation.py */
  const WORLD_Y_SCALE = 48;

  /** ~[-1, 1] smooth noise; used for slope and scaled for world Y. */
  function elevationRaw(tx, ty) {
    const fx = tx * 0.06;
    const fy = ty * 0.07;
    const low =
      Math.sin(fx + fy * 0.71) * 0.5 +
      Math.cos(fx * 0.55 - fy * 0.8) * 0.35 +
      Math.sin((tx + ty) * 0.095) * 0.15;
    const med =
      Math.sin(tx * 0.14 + ty * 0.11) * 0.12 + Math.cos(tx * 0.09 - ty * 0.13) * 0.08;
    const r = low + med;
    return Math.max(-1, Math.min(1, r));
  }

  /** Visual height in world units (Three.js Y). */
  function worldY(tx, ty) {
    return 2 + elevationRaw(tx, ty) * WORLD_Y_SCALE;
  }

  /**
   * Movement interval multiplier (1 = base speed).
   * Uphill (next tile higher) > 1 → slower; downhill < 1 → faster.
   */
  function moveIntervalMult(px, py, dir, worldW, worldH) {
    const w = worldW != null ? worldW : DEFAULT_W;
    const h = worldH != null ? worldH : DEFAULT_H;
    const d = { up: [0, -1], down: [0, 1], left: [-1, 0], right: [1, 0] }[dir];
    if (!d) return 1;
    const nx = px + d[0];
    const ny = py + d[1];
    if (nx < 0 || ny < 0 || nx >= w || ny >= h) return 1;
    const dh = elevationRaw(nx, ny) - elevationRaw(px, py);
    const m = 1 + 2.4 * dh;
    return Math.max(0.76, Math.min(1.24, m));
  }

  return { elevationRaw, worldY, moveIntervalMult };
})();
