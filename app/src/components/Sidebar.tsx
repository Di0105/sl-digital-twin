import type { MeasureMode, ModelRecord } from "../types";

export interface LayerState {
  imagery: boolean;
  terrain: boolean;
  models: boolean;
  labels: boolean;
}

interface Props {
  models: ModelRecord[];
  activeId: string | null;
  onSelect: (id: string) => void;
  layers: LayerState;
  onLayer: (key: keyof LayerState, value: boolean) => void;
  measureMode: MeasureMode;
  onMeasure: (mode: MeasureMode) => void;
  onClearMeasure: () => void;
  onReset: () => void;
}

const LAYER_LABELS: Record<keyof LayerState, string> = {
  imagery: "Satellite imagery",
  terrain: "Basemap globe",
  models: "Reality-mesh models",
  labels: "Model labels",
};

const MEASURE_LABELS: Record<MeasureMode, string> = {
  none: "",
  distance: "Distance",
  area: "Area",
  height: "Height",
};

export function Sidebar(props: Props) {
  const { models, activeId, onSelect, layers, onLayer, measureMode, onMeasure, onClearMeasure, onReset } = props;

  return (
    <div className="sidebar">
      <h1 className="title">Sri Lanka Digital Twin</h1>
      <p className="subtitle">Reality-mesh WebGIS · Cesium · UTM 44N (EPSG:32644+5773)</p>

      <div className="section-h">Models ({models.length})</div>
      {models.map((m) => (
        <div
          key={m.id}
          className={`model-item ${m.id === activeId ? "active" : ""}`}
          onClick={() => onSelect(m.id)}
        >
          <div className="model-dot" />
          <div>
            <div className="model-name">{m.label}</div>
            <div className="model-place">{m.region}</div>
          </div>
        </div>
      ))}

      <div className="section-h">Layers</div>
      {(Object.keys(LAYER_LABELS) as (keyof LayerState)[]).map((key) => (
        <label className="toggle-row" key={key}>
          {LAYER_LABELS[key]}
          <input type="checkbox" checked={layers[key]} onChange={(e) => onLayer(key, e.target.checked)} />
        </label>
      ))}

      <div className="section-h">Measure</div>
      <p className="hint">
        Left-click to add points, right-click to finish. Click the active mode again or <b>Clear</b> to erase and exit.
      </p>
      <div className="btn-row">
        {(["distance", "area", "height"] as MeasureMode[]).map((mode) => (
          <button
            key={mode}
            className={`btn ${measureMode === mode ? "active" : ""}`}
            onClick={() => onMeasure(mode)}
          >
            {MEASURE_LABELS[mode]}
          </button>
        ))}
        <button className="btn btn-clear" onClick={onClearMeasure}>
          Clear
        </button>
      </div>

      <div className="section-h">View</div>
      <button className="btn" onClick={onReset}>
        Reset to Sri Lanka
      </button>
    </div>
  );
}
