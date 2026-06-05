import { Ion, Math as CesiumMath } from "cesium";

/**
 * Cesium ion token is read from the gitignored .env (VITE_CESIUM_ION_TOKEN).
 * When absent the app still runs with token-free OpenStreetMap imagery and a
 * flat ellipsoid (no world terrain / terrain-snap).
 */
export const ION_TOKEN = (import.meta.env.VITE_CESIUM_ION_TOKEN ?? "").trim();
export const HAS_ION = ION_TOKEN.length > 0;

if (HAS_ION) {
  Ion.defaultAccessToken = ION_TOKEN;
}

/** Sri Lanka overview camera (whole island). */
export const SRI_LANKA_VIEW = {
  destination: { lon: 80.7, lat: 7.6, height: 480_000 },
  pitch: CesiumMath.toRadians(-90),
};
