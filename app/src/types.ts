/** Georeference registry record emitted by tools/sm_export/sm_to_3dtiles.py. */
export interface ModelRecord {
  id: string;
  name: string;
  label: string;
  place: string;
  region: string;
  source_3sm: string;
  srs: string;
  utm_zone: string;
  centroid_utm: { easting: number; northing: number; z_egm96: number };
  centroid_wgs84: {
    lon: number;
    lat: number;
    h_ellipsoidal: number;
    geoid_undulation_egm96: number;
  };
  ecef_origin: { x: number; y: number; z: number };
  bbox_local_enu_m: { min: [number, number, number]; max: [number, number, number] };
  gltf_axis_order?: string;
  base_height_local_m: number;
  top_height_local_m: number;
  vertices: number;
  triangles: number;
  leaf_nodes: number;
  georef_method: string;
  tileset: string;
  content: string;
}

export type MeasureMode = "none" | "distance" | "area" | "height";

export interface ProbeReading {
  lon: number;
  lat: number;
  heightEllipsoid: number;
  heightOrthometric: number;
  geoidUndulation: number;
  utmE: number;
  utmN: number;
}
