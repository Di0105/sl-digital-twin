import proj4 from "proj4";

// WGS84 / UTM zone 44N (the reality-mesh engine CRS) for the coordinate probe.
proj4.defs("EPSG:32644", "+proj=utm +zone=44 +datum=WGS84 +units=m +no_defs +type=crs");

const toUtm = proj4("EPSG:4326", "EPSG:32644");

/** lon/lat (deg) -> UTM zone 44N easting/northing (m). */
export function lonLatToUtm44(lon: number, lat: number): { e: number; n: number } {
  const [e, n] = toUtm.forward([lon, lat]);
  return { e, n };
}
