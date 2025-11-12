# We organize inputs by *format* and *origin* so our fuzzers can mutate each path independently and in cross-modal combinations.

**AP still frames (flight01)**

| index | image_path | cam_id | eo_row | ts_iso | width | height | has_exif | crc32 |
|---:|---|---|---:|---|---:|---:|:---:|:---:|
| 0 | `AP/frames/flight01/f01_000000.jpg` | FX35 | 0 | 2025-11-10T09:12:20Z | 5472 | 3648 | 1 | `0x8A3E1C2B` |
| 1 | `AP/frames/flight01/f01_000001.jpg` | FX35 | 1 | 2025-11-10T09:12:22Z | 5472 | 3648 | 1 | `0x4C7F2E10` |
| 2 | `AP/frames/flight01/f01_000002.jpg` | FX35 | 2 | 2025-11-10T09:12:24Z | 5472 | 3648 | 1 | `0xD1A09755` |
| 3 | `AP/frames/flight01/f01_000003.jpg` | FX35 | 3 | 2025-11-10T09:12:26Z | 5472 | 3648 | 1 | `0x6B20A4B8` |
| 4 | `AP/frames/flight01/f01_000004.jpg` | FX35 | 4 | 2025-11-10T09:12:28Z | 5472 | 3648 | 1 | `0xF0C93211` |

**Video frames (gopro_corridor01.mp4 → decoded @2 FPS)**

| index | source | frame_id | extracted_path | ts_ms | w×h | keyframe | crc32 |
|---:|---|---|---|---:|---:|:---:|:---:|
| 0 | `STREAMS/gopro_corridor01.mp4` | 000000 | `cache/vid/gopro_corridor01/000000.jpg` | 0 | 3840×2160 | ✓ | `0x7D51B11C` |
| 1 | `STREAMS/gopro_corridor01.mp4` | 000001 | `cache/vid/gopro_corridor01/000001.jpg` | 500 | 3840×2160 |  | `0xAEE1F913` |
| 2 | `STREAMS/gopro_corridor01.mp4` | 000002 | `cache/vid/gopro_corridor01/000002.jpg` | 1000 | 3840×2160 |  | `0xC1970B65` |
| 3 | `STREAMS/gopro_corridor01.mp4` | 000003 | `cache/vid/gopro_corridor01/000003.jpg` | 1500 | 3840×2160 |  | `0x1F0D2A42` |
| 4 | `STREAMS/gopro_corridor01.mp4` | 000004 | `cache/vid/gopro_corridor01/000004.jpg` | 2000 | 3840×2160 |  | `0x6B917C0F` |

**ALS tiles (voxelized previews for quick fuzz loops)**

| index | laz_path | pts | bounds_xyz | density_est (pts/m²) | has_rgb | has_intensity | has_returns | crc32 |
|---:|---|---:|---|---:|:---:|:---:|:---:|:---:|
| 0 | `ALS/point_cloud.laz` | 117,736,285 | [1237029…1238716, 12090305…12094471, 58.3…174.7] | 16.75 | ✓ | ✓ | ✓ | `0x9F2245A1` |
| 1 | `ALS/segment_A.laz` | 32,119,004 | [1237200…1237900, …] | 18.10 | ✓ | ✓ | ✓ | `0x12B7CC39` |
| 2 | `ALS/segment_B.laz` | 44,983,700 | [1237900…1238600, …] | 15.02 | ✓ | ✓ | ✓ | `0xE9057C21` |

---

## Fuzz Targets & Mutation Operators

### ALS (.laz)
- **Header mutations:** bogus point count; missing CRS; scale/offset jitter; return count overflow.
- **Point payload:** random NaNs/Inf; z-offset spikes; RGB nulling; intensity clipping; return order shuffle.
- **Spatial structure:** scramble block ordering; inject dense “needle” clusters; drop thin wire points.

### AP (stills) & EO
- **JPEG:** recompress at extreme Q; EXIF strip; random color cast; Gaussian/Poisson noise; image truncation.
- **EO rows:** swap Omega/Phi/Kappa; jitter orientation ±15°; time skew; drop camera rows; CRS mismatch.

### Video streams
- **Frame rate:** variable decode; dropped keyframes; duplicate frames; GOP corruption.
- **RTSP:** latency spikes; packet loss; H.264 SPS/PPS anomalies; resolution renegotiation mid-stream.

### Rasters (DTM/DSM/Ortho)
- **Nodata toggling;** edge padding; scale resample with misaligned geotransform; band order swap.

---

Coverage-Guided Fuzz Harness

We treat the pipeline as a function `run_job(cfg)` and instrument:
- **Python coverage** for our glue code (pytest-cov).
- **Native coverage** for PDAL/GDAL codepaths via sentinel assertions/regression oracles.
- **Semantic oracles** (see §6) to label pass/fail on geometry & schema.

---

**CLI**

```bash
# Dry-run corpus build
python tools/fuzz_corpus_build.py --als ALS --ap AP/frames --eo AP/EO --out corpus/

# Coverage-guided fuzzing
python tools/fuzz_runner.py \
  --corpus corpus/ \
  --iters 2000 \
  --mutators als,ap,eo,video,rasters \
  --timeout-sec 900 \
  --out reports/fuzz_logs/
```
---

### Failure detection

```
Case: fz_2025_11_12_00471
Trigger: AP EO row swap + JPEG quality 8
Stage: features
Error: Insulator clustering diverged (crossarm band not detected)

Minimization:
  - EO delta: kept only rows {213, 214}
  - Image crop: 1024×768 around tower top
  - JPEG Q: 8 → 12 (still fails)
Reproducer:
  repro/ap_fail/min_f01_000214_q12.jpg
  repro/ap_fail/min_f01_213_214.csv
```
---

## Output

| run_id               | seed | kind   | outcome         | stage       | miou_wire | hausdorff_m | tilt_rmse_deg | notes          |
|----------------------|:----:|--------|-----------------|-------------|:---------:|:-----------:|:-------------:|----------------|
| fz_2025_11_12_00123 | 2025 | ALS    | PASS_WITH_WARN  | export      |  0.915    |    0.031    |     0.52      | CRS defaulted  |
| fz_2025_11_12_00471 | 1337 | AP+EO  | FAIL            | features    |  0.710    |    0.190    |     0.98      | EO row swap    |
| fz_2025_11_12_00590 |   7  | STREAM | PASS            | reconstruct |  0.927    |    0.036    |     0.61      | 10% drop       |

---
