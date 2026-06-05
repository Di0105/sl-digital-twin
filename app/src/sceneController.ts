import {
  BoundingSphere,
  Cartesian2,
  Cartesian3,
  Cartographic,
  Color,
  HeadingPitchRange,
  Math as CesiumMath,
  Matrix4,
  Transforms,
  ScreenSpaceEventHandler,
  ScreenSpaceEventType,
  Cesium3DTileset,
  Ellipsoid,
  sampleTerrainMostDetailed,
  defined,
  LabelStyle,
  VerticalOrigin,
  NearFarScalar,
  type Viewer,
  type Entity,
} from "cesium";
import type { ModelRecord, ProbeReading } from "./types";
import { lonLatToUtm44 } from "./proj";

const LABEL_COLOR = Color.fromCssColorString("#ffb703");
const TERRAIN_CLEARANCE_M = 1.5;

function appAssetUrl(path: string): string {
  return `${import.meta.env.BASE_URL}${path.replace(/^\/+/, "")}`;
}

export class SceneController {
  readonly viewer: Viewer;
  models: ModelRecord[] = [];
  private tilesets = new Map<string, Cesium3DTileset>();
  private labels = new Map<string, Entity>();
  private snapOffset = new Map<string, number>();
  private probeHandler?: ScreenSpaceEventHandler;
  activeId: string | null = null;

  constructor(viewer: Viewer) {
    this.viewer = viewer;
    viewer.scene.globe.depthTestAgainstTerrain = false;
    viewer.scene.screenSpaceCameraController.enableCollisionDetection = false;
    viewer.scene.screenSpaceCameraController.minimumZoomDistance = 1;
  }

  async loadRegistry(): Promise<ModelRecord[]> {
    const res = await fetch(appAssetUrl("tiles/registry.json"));
    this.models = (await res.json()) as ModelRecord[];
    for (const m of this.models) this.addLabel(m);
    return this.models;
  }

  private addLabel(m: ModelRecord): void {
    const { lon, lat } = m.centroid_wgs84;
    const entity = this.viewer.entities.add({
      id: `label-${m.id}`,
      position: Cartesian3.fromDegrees(lon, lat, 0),
      point: { pixelSize: 11, color: LABEL_COLOR, outlineColor: Color.BLACK, outlineWidth: 2 },
      label: {
        text: m.label,
        font: "13px Segoe UI, sans-serif",
        fillColor: Color.WHITE,
        style: LabelStyle.FILL_AND_OUTLINE,
        outlineColor: Color.BLACK,
        outlineWidth: 3,
        verticalOrigin: VerticalOrigin.BOTTOM,
        pixelOffset: new Cartesian2(0, -14),
        scaleByDistance: new NearFarScalar(2_000, 1.0, 400_000, 0.5),
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
    });
    this.labels.set(m.id, entity);
  }

  /** Click a model: fly top-down to it, then auto-tilt to an oblique near view. */
  async selectModel(id: string): Promise<void> {
    const m = this.models.find((x) => x.id === id);
    if (!m) return;
    this.activeId = id;
    const tileset = await this.ensureTileset(m);
    const sphere = this.visualBoundingSphere(m, tileset);
    await this.flyToSafeOverview(m, sphere);
    const range = Math.max(sphere.radius * 3.0, 180);
    this.viewer.camera.flyToBoundingSphere(sphere, {
      duration: 1.4,
      offset: new HeadingPitchRange(CesiumMath.toRadians(35), CesiumMath.toRadians(-28), range),
    });
  }

  private flyToSafeOverview(m: ModelRecord, sphere: BoundingSphere): Promise<void> {
    const topHeight = m.centroid_wgs84.h_ellipsoidal + this.getSnapOffset(m.id) + m.top_height_local_m;
    const safeHeight = topHeight + Math.max(sphere.radius * 5, 350);
    return new Promise((resolve) => {
      this.viewer.camera.flyTo({
        destination: Cartesian3.fromDegrees(m.centroid_wgs84.lon, m.centroid_wgs84.lat, safeHeight),
        orientation: { heading: 0, pitch: CesiumMath.toRadians(-80), roll: 0 },
        duration: 0.8,
        complete: () => resolve(),
        cancel: () => resolve(),
      });
    });
  }

  async ensureTileset(m: ModelRecord): Promise<Cesium3DTileset> {
    const existing = this.tilesets.get(m.id);
    if (existing) return existing;
    const tileset = await Cesium3DTileset.fromUrl(appAssetUrl(`tiles/${m.id}/tileset.json`), {
      maximumScreenSpaceError: 2,
    });
    this.viewer.scene.primitives.add(tileset);
    this.tilesets.set(m.id, tileset);
    await this.terrainSnap(m, tileset);
    return tileset;
  }

  private visualBoundingSphere(m: ModelRecord, tileset: Cesium3DTileset): BoundingSphere {
    const min = m.bbox_local_enu_m.min;
    const max = m.bbox_local_enu_m.max;
    const centerUp = (min[2] + max[2]) / 2;
    const centerHeight = m.centroid_wgs84.h_ellipsoidal + this.getSnapOffset(m.id) + centerUp;
    const center = Cartesian3.fromDegrees(m.centroid_wgs84.lon, m.centroid_wgs84.lat, centerHeight);
    const dx = max[0] - min[0];
    const dy = max[1] - min[1];
    const dz = max[2] - min[2];
    const radius = Math.max(Math.sqrt(dx * dx + dy * dy + dz * dz) / 2, tileset.boundingSphere.radius);
    return new BoundingSphere(center, radius);
  }

  /** Vertically translate the tileset so its base sits on sampled terrain. */
  private async terrainSnap(m: ModelRecord, tileset: Cesium3DTileset): Promise<void> {
    const { lon, lat, h_ellipsoidal } = m.centroid_wgs84;
    const baseHEll = h_ellipsoidal + m.base_height_local_m;
    let terrainH = 0;
    try {
      const sampled = await sampleTerrainMostDetailed(this.viewer.terrainProvider, this.terrainFootprintSamples(m));
      const heights = sampled.map((carto) => carto.height).filter((height): height is number => defined(height));
      if (heights.length > 0) terrainH = Math.max(...heights);
    } catch {
      /* no terrain provider -> snap to ellipsoid 0 */
    }
    const offset = terrainH + TERRAIN_CLEARANCE_M - baseHEll;
    this.snapOffset.set(m.id, offset);
    const normal = Ellipsoid.WGS84.geodeticSurfaceNormalCartographic(Cartographic.fromDegrees(lon, lat));
    tileset.modelMatrix = Matrix4.fromTranslation(Cartesian3.multiplyByScalar(normal, offset, new Cartesian3()));
  }

  private terrainFootprintSamples(m: ModelRecord): Cartographic[] {
    const { lon, lat, h_ellipsoidal } = m.centroid_wgs84;
    const origin = Cartesian3.fromDegrees(lon, lat, h_ellipsoidal);
    const frame = Transforms.eastNorthUpToFixedFrame(origin);
    const min = m.bbox_local_enu_m.min;
    const max = m.bbox_local_enu_m.max;
    const cx = (min[0] + max[0]) / 2;
    const cy = (min[1] + max[1]) / 2;
    const points = [
      [cx, cy],
      [min[0], min[1]],
      [min[0], cy],
      [min[0], max[1]],
      [cx, min[1]],
      [cx, max[1]],
      [max[0], min[1]],
      [max[0], cy],
      [max[0], max[1]],
    ];
    return points.map(([east, north]) => {
      const fixed = Matrix4.multiplyByPoint(frame, new Cartesian3(east, north, 0), new Cartesian3());
      return Cartographic.fromCartesian(fixed);
    });
  }

  getSnapOffset(id: string): number {
    return this.snapOffset.get(id) ?? 0;
  }

  setTilesetVisible(id: string, visible: boolean): void {
    const t = this.tilesets.get(id);
    if (t) t.show = visible;
  }

  setAllTilesetsVisible(visible: boolean): void {
    for (const t of this.tilesets.values()) t.show = visible;
  }

  setLabelsVisible(visible: boolean): void {
    for (const e of this.labels.values()) e.show = visible;
  }

  highlightSelected(_id: string | null): void {
    for (const t of this.tilesets.values()) t.style = undefined;
  }

  /** Stream lon/lat/height/UTM under the cursor to a callback. */
  enableProbe(cb: (r: ProbeReading | null) => void): void {
    this.probeHandler?.destroy();
    const handler = new ScreenSpaceEventHandler(this.viewer.scene.canvas);
    handler.setInputAction((movement: { endPosition: Cartesian2 }) => {
      const scene = this.viewer.scene;
      let cart = scene.pickPosition(movement.endPosition);
      if (!defined(cart)) {
        cart = this.viewer.camera.pickEllipsoid(movement.endPosition, Ellipsoid.WGS84) as Cartesian3;
      }
      if (!defined(cart)) return cb(null);
      const c = Cartographic.fromCartesian(cart);
      const lon = CesiumMath.toDegrees(c.longitude);
      const lat = CesiumMath.toDegrees(c.latitude);
      const { e, n } = lonLatToUtm44(lon, lat);
      const geoid = this.nearestGeoidUndulation(lon, lat);
      cb({
        lon,
        lat,
        heightEllipsoid: c.height,
        heightOrthometric: c.height - geoid,
        geoidUndulation: geoid,
        utmE: e,
        utmN: n,
      });
    }, ScreenSpaceEventType.MOUSE_MOVE);
    this.probeHandler = handler;
  }

  private nearestGeoidUndulation(lon: number, lat: number): number {
    let nearest = this.models[0];
    let best = Number.POSITIVE_INFINITY;
    for (const model of this.models) {
      const dx = lon - model.centroid_wgs84.lon;
      const dy = lat - model.centroid_wgs84.lat;
      const dist2 = dx * dx + dy * dy;
      if (dist2 < best) {
        best = dist2;
        nearest = model;
      }
    }
    return nearest?.centroid_wgs84.geoid_undulation_egm96 ?? 0;
  }

  resetView(): void {
    this.activeId = null;
    this.viewer.camera.flyTo({
      destination: Cartesian3.fromDegrees(80.7, 7.6, 480_000),
      orientation: { heading: 0, pitch: CesiumMath.toRadians(-90), roll: 0 },
      duration: 1.8,
    });
  }

  destroy(): void {
    this.probeHandler?.destroy();
  }
}
