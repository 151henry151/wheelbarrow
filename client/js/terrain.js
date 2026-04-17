/**
 * Rolling elevation (shared server formula in server/game/terrain_elevation.py).
 * Mild hills — height is smooth across tile integer coords.
 */
const Terrain = (() => {
  const DEFAULT_W = 1000;
  const DEFAULT_H = 1000;

  /** ~[-1, 1] smooth noise; used for slope and scaled for world Y. */
  function elevationRaw(tx, ty) {
    const fx = tx * 0.06;
    const fy = ty * 0.07;
    return (
      Math.sin(fx + fy * 0.71) * 0.5 +
      Math.cos(fx * 0.55 - fy * 0.8) * 0.35 +
      Math.sin((tx + ty) * 0.095) * 0.15
    );
  }

  /** Visual height in world units (Three.js Y). Stronger than server elevation_raw scale for readability. */
  function worldY(tx, ty) {
    return 2 + elevationRaw(tx, ty) * 12;
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
