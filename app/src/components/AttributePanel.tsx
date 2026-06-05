import type { ModelRecord } from "../types";

interface Props {
  record: ModelRecord;
  snapOffset: number;
  onClose: () => void;
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="attr-row">
      <span>{k}</span>
      <span>{v}</span>
    </div>
  );
}

export function AttributePanel({ record, snapOffset, onClose }: Props) {
  const w = record.centroid_wgs84;
  const u = record.centroid_utm;
  const visualBaseEllipsoid = w.h_ellipsoidal + record.base_height_local_m + snapOffset;
  const visualBaseOrthometric = visualBaseEllipsoid - w.geoid_undulation_egm96;
  return (
    <div className="attr">
      <button className="attr-close" onClick={onClose}>
        ✕
      </button>
      <h2 className="title">{record.label}</h2>
      <p className="subtitle">
        {record.place} · <span className="pill">georeferenced</span>
      </p>

      <div className="attr-group">
        <div className="section-h">Coordinates &amp; CRS</div>
        <Row k="Longitude" v={`${w.lon.toFixed(6)}°`} />
        <Row k="Latitude" v={`${w.lat.toFixed(6)}°`} />
        <Row k="UTM 44N Easting" v={`${u.easting.toFixed(2)} m`} />
        <Row k="UTM 44N Northing" v={`${u.northing.toFixed(2)} m`} />
        <Row k="Source h (WGS84 ellipsoid)" v={`${w.h_ellipsoidal.toFixed(2)} m`} />
        <Row k="Source H (EGM96 / DTM)" v={`${u.z_egm96.toFixed(2)} m`} />
        <Row k="Geoid undulation N" v={`${w.geoid_undulation_egm96.toFixed(2)} m`} />
        <Row k="Horizontal CRS" v="EPSG:32644" />
        <Row k="Vertical datum" v="EGM96 (EPSG:5773)" />
        <Row k="Visual base H (EGM96)" v={`${visualBaseOrthometric.toFixed(2)} m`} />
        <Row k="Datum/snap offset" v={`${snapOffset.toFixed(2)} m`} />
      </div>

      <div className="attr-group">
        <div className="section-h">Model metadata</div>
        <Row k="Format" v="3D Tiles 1.1 (glTF / GLB)" />
        <Row k="Source" v=".3sm reality mesh" />
        <Row k="Capture" v="UAV photogrammetry" />
        <Row k="Georef method" v="drone GPS, no GCP/RTK" />
        <Row k="Leaf nodes" v={`${record.leaf_nodes}`} />
        <Row k="Vertices" v={record.vertices.toLocaleString()} />
        <Row k="Triangles" v={record.triangles.toLocaleString()} />
        <Row k="Accuracy" v="~1–5 m H, ~5–10 m V" />
      </div>

      <div className="attr-group">
        <div className="section-h">ECEF origin (EPSG:4978)</div>
        <Row k="X" v={`${record.ecef_origin.x.toFixed(2)} m`} />
        <Row k="Y" v={`${record.ecef_origin.y.toFixed(2)} m`} />
        <Row k="Z" v={`${record.ecef_origin.z.toFixed(2)} m`} />
      </div>
    </div>
  );
}
