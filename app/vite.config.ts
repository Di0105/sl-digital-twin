import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import cesium from "vite-plugin-cesium";
import { createReadStream, existsSync, statSync } from "node:fs";
import { extname, join, normalize } from "node:path";

const TILES_DIR = normalize(join(__dirname, "..", "tiles"));
const BASE_PATH = process.env.GITHUB_PAGES_BASE ?? "/";

const MIME: Record<string, string> = {
  ".json": "application/json",
  ".glb": "model/gltf-binary",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".png": "image/png",
  ".b3dm": "application/octet-stream",
};

/**
 * Serve the externally-generated 3D Tiles folder (../tiles) at the /tiles
 * route during dev so the large meshes are not duplicated into public/.
 *
 * Supports HTTP Range requests and always sets Content-Length so large GLB
 * meshes (tens of MB) stream to completion instead of being truncated, which
 * would make Cesium parse only part of the mesh ("fragmented" model).
 */
function serveTiles(): Plugin {
  return {
    name: "serve-tiles",
    configureServer(server) {
      server.middlewares.use("/tiles", (req, res, next) => {
        const rel = decodeURIComponent((req.url ?? "/").split("?")[0]);
        const file = normalize(join(TILES_DIR, rel));
        if (!file.startsWith(TILES_DIR) || !existsSync(file) || !statSync(file).isFile()) {
          return next();
        }

        const size = statSync(file).size;
        const type = MIME[extname(file).toLowerCase()] ?? "application/octet-stream";
        res.setHeader("Content-Type", type);
        res.setHeader("Access-Control-Allow-Origin", "*");
        res.setHeader("Accept-Ranges", "bytes");
        res.setHeader("Cache-Control", "no-cache");

        const range = req.headers.range;
        if (range) {
          const m = /^bytes=(\d*)-(\d*)$/.exec(range);
          if (m) {
            const start = m[1] ? parseInt(m[1], 10) : 0;
            const end = m[2] ? parseInt(m[2], 10) : size - 1;
            if (start >= size || end >= size || start > end) {
              res.statusCode = 416;
              res.setHeader("Content-Range", `bytes */${size}`);
              return res.end();
            }
            res.statusCode = 206;
            res.setHeader("Content-Range", `bytes ${start}-${end}/${size}`);
            res.setHeader("Content-Length", end - start + 1);
            return createReadStream(file, { start, end }).pipe(res);
          }
        }

        res.statusCode = 200;
        res.setHeader("Content-Length", size);
        if (req.method === "HEAD") return res.end();
        createReadStream(file).pipe(res);
      });
    },
  };
}

export default defineConfig({
  base: BASE_PATH,
  plugins: [react(), cesium(), serveTiles()],
  server: { port: 5173, open: true },
});
