import { useEffect, useRef, useState } from "react";
import { Viewer as ResiumViewer, type CesiumComponentRef } from "resium";
import {
  Viewer as CesiumViewer,
  UrlTemplateImageryProvider,
} from "cesium";
import { HAS_ION } from "./cesiumConfig";
import { SceneController } from "./sceneController";
import { MeasureTool } from "./measure";
import type { MeasureMode, ModelRecord, ProbeReading } from "./types";
import { Sidebar, type LayerState } from "./components/Sidebar";
import { AttributePanel } from "./components/AttributePanel";

const DEFAULT_LAYERS: LayerState = { imagery: true, terrain: true, models: true, labels: true };

export default function App() {
  const ref = useRef<CesiumComponentRef<CesiumViewer>>(null);
  const ctrlRef = useRef<SceneController | null>(null);
  const measureRef = useRef<MeasureTool | null>(null);

  const [models, setModels] = useState<ModelRecord[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [probe, setProbe] = useState<ProbeReading | null>(null);
  const [measureMode, setMeasureMode] = useState<MeasureMode>("none");
  const [measureText, setMeasureText] = useState<string | null>(null);
  const [snapOffsets, setSnapOffsets] = useState<Record<string, number>>({});
  const [layers, setLayers] = useState<LayerState>(DEFAULT_LAYERS);

  useEffect(() => {
    let cancelled = false;
    const t = setInterval(async () => {
      const viewer = ref.current?.cesiumElement;
      if (!viewer || ctrlRef.current) return;
      clearInterval(t);

      // Satellite imagery on a flat WGS84 ellipsoid. Cesium World Terrain is
      // intentionally NOT used: the local drone-GPS reality meshes disagree with
      // the global DTM (geoid undulation ~-99 m at Galle), which buries and
      // black-renders the buildings. Each mesh is snapped just above the
      // imagery-draped ellipsoid instead.
      // Cesium ion's Bing-based World Imagery was retired, so always use the
      // token-free Esri World Imagery (reliable satellite, not OSM road tiles).
      // The ion token, when present, only hides the banner / enables ion assets.
      viewer.imageryLayers.addImageryProvider(
        new UrlTemplateImageryProvider({
          url:
            "https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
          maximumLevel: 19,
          credit: "Imagery (c) Esri, Maxar, Earthstar Geographics",
        })
      );
      if (cancelled) return;

      const ctrl = new SceneController(viewer);
      ctrlRef.current = ctrl;
      measureRef.current = new MeasureTool(viewer, setMeasureText, setMeasureMode);
      ctrl.resetView();
      ctrl.enableProbe(setProbe);
      const recs = await ctrl.loadRegistry();
      if (!cancelled) setModels(recs);
    }, 120);
    return () => {
      cancelled = true;
      clearInterval(t);
      measureRef.current?.destroy();
      ctrlRef.current?.destroy();
    };
  }, []);

  const selectModel = async (id: string) => {
    setActiveId(id);
    const ctrl = ctrlRef.current;
    await ctrl?.selectModel(id);
    ctrl?.highlightSelected(id);
    if (ctrl) {
      setSnapOffsets((current) => ({ ...current, [id]: ctrl.getSnapOffset(id) }));
    }
  };

  const updateLayer = (key: keyof LayerState, value: boolean) => {
    setLayers((s) => ({ ...s, [key]: value }));
    const ctrl = ctrlRef.current;
    if (!ctrl) return;
    if (key === "models") ctrl.setAllTilesetsVisible(value);
    if (key === "labels") ctrl.setLabelsVisible(value);
    if (key === "imagery") ctrl.viewer.imageryLayers.get(0).show = value;
    if (key === "terrain") ctrl.viewer.scene.globe.show = value;
  };

  const setMeasure = (mode: MeasureMode) => {
    const next = mode === measureMode ? "none" : mode;
    setMeasureMode(next);
    measureRef.current?.setMode(next);
  };

  const clearMeasure = () => {
    measureRef.current?.cancel();
  };

  const reset = () => {
    setActiveId(null);
    setMeasure("none");
    ctrlRef.current?.resetView();
    ctrlRef.current?.highlightSelected(null);
  };

  const selected = models.find((m) => m.id === activeId) ?? null;

  return (
    <div className="app">
      <ResiumViewer
        ref={ref}
        full
        baseLayer={false as never}
        baseLayerPicker={false}
        geocoder={false}
        homeButton={false}
        sceneModePicker={false}
        navigationHelpButton={false}
        animation={false}
        timeline={false}
        fullscreenButton={false}
        infoBox={false}
        selectionIndicator={false}
      />

      <Sidebar
        models={models}
        activeId={activeId}
        onSelect={selectModel}
        layers={layers}
        onLayer={updateLayer}
        measureMode={measureMode}
        onMeasure={setMeasure}
        onClearMeasure={clearMeasure}
        onReset={reset}
      />

      {selected && (
        <AttributePanel
          record={selected}
          snapOffset={snapOffsets[selected.id] ?? ctrlRef.current?.getSnapOffset(selected.id) ?? 0}
          onClose={() => {
            setActiveId(null);
            ctrlRef.current?.highlightSelected(null);
          }}
        />
      )}

      {probe && (
        <div className="probe">
          <span>
            lon <b>{probe.lon.toFixed(6)}°</b>
          </span>
          <span>
            lat <b>{probe.lat.toFixed(6)}°</b>
          </span>
          <span>
            H(EGM96) <b>{probe.heightOrthometric.toFixed(1)} m</b>
          </span>
          <span>
            h(WGS84) <b>{probe.heightEllipsoid.toFixed(1)} m</b>
          </span>
          <span>
            UTM44N <b>{probe.utmE.toFixed(1)}E {probe.utmN.toFixed(1)}N</b>
          </span>
        </div>
      )}

      {measureText && <div className="measure-readout">{measureText}</div>}

      {!HAS_ION && (
        <div className="no-token">
          No Cesium ion token in <code>.env</code> — using Esri World Imagery on a flat ellipsoid
          (no world terrain / terrain-snap). Add <code>VITE_CESIUM_ION_TOKEN</code> and restart for
          Cesium World Imagery.
        </div>
      )}
    </div>
  );
}