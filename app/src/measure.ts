import {
  Cartesian3,
  Cartographic,
  Color,
  Math as CesiumMath,
  ScreenSpaceEventHandler,
  ScreenSpaceEventType,
  Transforms,
  Matrix4,
  CallbackProperty,
  PolygonHierarchy,
  defined,
  type Cartesian2,
  type Viewer,
  type Entity,
} from "cesium";
import type { MeasureMode } from "./types";

/** Interactive distance / area / height-difference measurement. */
export class MeasureTool {
  private viewer: Viewer;
  private handler?: ScreenSpaceEventHandler;
  private points: Cartesian3[] = [];
  private entities: Entity[] = [];
  private mode: MeasureMode = "none";
  private cb: (text: string | null) => void;
  private setActiveMode: (mode: MeasureMode) => void;
  private readonly preventContextMenu = (event: Event) => event.preventDefault();

  constructor(viewer: Viewer, cb: (text: string | null) => void, setActiveMode: (mode: MeasureMode) => void) {
    this.viewer = viewer;
    this.cb = cb;
    this.setActiveMode = setActiveMode;
  }

  setMode(mode: MeasureMode): void {
    this.stopHandler();
    this.clearEntities();
    this.mode = mode;
    this.setActiveMode(mode);
    if (mode === "none") {
      this.cb(null);
      return;
    }
    const handler = new ScreenSpaceEventHandler(this.viewer.scene.canvas);
    handler.setInputAction((m: { position: Cartesian2 }) => this.addPoint(m.position), ScreenSpaceEventType.LEFT_CLICK);
    handler.setInputAction(() => this.finish(), ScreenSpaceEventType.RIGHT_CLICK);
    this.handler = handler;
    this.viewer.scene.canvas.addEventListener("contextmenu", this.preventContextMenu);
    this.cb(this.hint());
  }

  private hint(): string {
    if (this.mode === "distance") return "Distance: left-click points, right-click to finish; click Distance again or Clear to cancel";
    if (this.mode === "area") return "Area: left-click polygon vertices, right-click to finish; click Clear to cancel";
    return "Height: left-click two points; click Clear to cancel";
  }

  private pick(pos: Cartesian2): Cartesian3 | undefined {
    const scene = this.viewer.scene;
    const c = scene.pickPosition(pos);
    return defined(c) ? c : this.viewer.camera.pickEllipsoid(pos);
  }

  private addPoint(pos: Cartesian2): void {
    const c = this.pick(pos);
    if (!defined(c)) return;
    this.points.push(c);
    this.entities.push(
      this.viewer.entities.add({
        position: c,
        point: { pixelSize: 8, color: Color.fromCssColorString("#ffb703"), disableDepthTestDistance: Number.POSITIVE_INFINITY },
      })
    );
    if (this.points.length === 1 && this.mode !== "height") this.drawDynamic();
    if (this.mode === "height" && this.points.length === 2) this.finish();
    this.update();
  }

  private drawDynamic(): void {
    if (this.mode === "distance") {
      this.entities.push(
        this.viewer.entities.add({
          polyline: {
            positions: new CallbackProperty(() => this.points, false),
            width: 2.5,
            material: Color.fromCssColorString("#ffb703"),
            clampToGround: false,
          },
        })
      );
    } else if (this.mode === "area") {
      this.entities.push(
        this.viewer.entities.add({
          polygon: {
            hierarchy: new CallbackProperty(() => new PolygonHierarchy(this.points), false),
            material: Color.fromCssColorString("#ffb703").withAlpha(0.3),
            outline: true,
            outlineColor: Color.fromCssColorString("#ffb703"),
          },
        })
      );
    }
  }

  private update(): void {
    if (this.mode === "distance" && this.points.length >= 2) {
      let d = 0;
      for (let i = 1; i < this.points.length; i++) d += Cartesian3.distance(this.points[i - 1], this.points[i]);
      this.cb(`3D distance: ${d.toFixed(2)} m  (${this.points.length} pts)`);
    } else if (this.mode === "area" && this.points.length >= 3) {
      this.cb(`Area: ${this.planarArea().toFixed(2)} m²  (${this.points.length} pts)`);
    } else if (this.mode === "height" && this.points.length === 2) {
      const h0 = Cartographic.fromCartesian(this.points[0]).height;
      const h1 = Cartographic.fromCartesian(this.points[1]).height;
      this.cb(`Height difference: ${Math.abs(h1 - h0).toFixed(2)} m`);
    }
  }

  /** Shoelace area in a local ENU plane anchored at the first vertex. */
  private planarArea(): number {
    const origin = this.points[0];
    const toLocal = Matrix4.inverse(Transforms.eastNorthUpToFixedFrame(origin), new Matrix4());
    const pts = this.points.map((p) => Matrix4.multiplyByPoint(toLocal, p, new Cartesian3()));
    let a = 0;
    for (let i = 0; i < pts.length; i++) {
      const j = (i + 1) % pts.length;
      a += pts[i].x * pts[j].y - pts[j].x * pts[i].y;
    }
    return Math.abs(a) / 2;
  }

  private finish(): void {
    this.update();
    this.stopHandler();
    this.mode = "none";
    this.setActiveMode("none");
  }

  clear(): void {
    this.clearEntities();
    this.cb(null);
  }

  cancel(): void {
    this.stopHandler();
    this.clear();
    this.mode = "none";
    this.setActiveMode("none");
  }

  private clearEntities(): void {
    for (const e of this.entities) this.viewer.entities.remove(e);
    this.entities = [];
    this.points = [];
  }

  private stopHandler(): void {
    this.handler?.destroy();
    this.handler = undefined;
    this.viewer.scene.canvas.removeEventListener("contextmenu", this.preventContextMenu);
  }

  destroy(): void {
    this.cancel();
  }
}

export const fmtDeg = (v: number): string => `${v.toFixed(6)}°`;
export const fmtM = (v: number): string => `${v.toFixed(1)} m`;
export const radToDeg = CesiumMath.toDegrees;
