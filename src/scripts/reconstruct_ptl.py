import argparse, yaml
from pathlib import Path
import pandas as pd
import numpy as np
from sklearn.cluster import DBSCAN
from shapely.geometry import Point, LineString
import geopandas as gpd

CRS = "EPSG:32643"

def load_cfg(p): 
    import yaml; from pathlib import Path
    return yaml.safe_load(Path(p).read_text())

def pca_axis(xyz):
    # returns unit vertical-ish axis and endpoints
    X = xyz - xyz.mean(0)
    U,S,Vt = np.linalg.svd(X, full_matrices=False)
    axis = Vt[0]
    p0 = xyz.min(0); p1 = xyz.max(0)
    return axis, p0, p1

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cfg", required=True)
    args = ap.parse_args()
    cfg = load_cfg(args.cfg)
    out_root = Path(cfg["paths"]["out_root"])

    df = pd.read_parquet(out_root/"preds/labeled_points.parquet")
    # towers: label==1
    towers_df = df[df["label"]==1][["x","y","z"]].to_numpy()
    clustering = DBSCAN(eps=3.5, min_samples=50).fit(towers_df[:,:2])
    labels = clustering.labels_
    tower_axes = []
    insulators = []
    wid = 6.0

    for k in np.unique(labels):
        if k < 0: continue
        pts = towers_df[labels==k]
        if len(pts) < 200: continue
        axis, p0, p1 = pca_axis(pts)
        # vertical-ish line (take centroid x,y; base/top z)
        cx, cy = pts[:,0].mean(), pts[:,1].mean()
        zmin, zmax = pts[:,2].min(), pts[:,2].max()
        axis_geom = LineString([(cx, cy, zmin), (cx, cy, zmax)])
        tower_axes.append({"id": len(tower_axes)+1, "id_tower": len(tower_axes)+100, 
                           "height": float(zmax-zmin), "tilt_deg": 1.0, "geometry": axis_geom})

        # crude crossarm at near top
        z_attach = zmax - 1.2
        for slot, dx in enumerate([-wid, 0.0, wid]):
            insulators.append({
                "id": len(insulators)+1, "id_tower": len(tower_axes)+99,
                "id_wire": 1000 + len(insulators)+1, "slot": slot,
                "elevation_m": float(z_attach),
                "geometry": Point(cx+dx, cy, z_attach)
            })

    gdf_t = gpd.GeoDataFrame(tower_axes, crs=CRS, geometry="geometry")
    gdf_i = gpd.GeoDataFrame(insulators, crs=CRS, geometry="geometry")

    # wires: connect insulators by slot in tower order
    wire_rows=[]
    # group by slot
    for slot in (0,1,2):
        rows = gdf_i[gdf_i["slot"]==slot].sort_values("id_tower")
        coords = [(r.geometry.x, r.geometry.y, r.geometry.z) for _,r in rows.iterrows()]
        # build spans between consecutive towers
        for a,b in zip(coords[:-1], coords[1:]):
            # simple catenary-ish arc in 3D
            n=120
            xs = np.linspace(a[0], b[0], n)
            ys = np.linspace(a[1], b[1], n)
            zs = np.linspace(a[2], b[2], n) - 0.5*np.sin(np.linspace(0,np.pi,n)) # sag
            line = LineString([(xs[i],ys[i],float(zs[i])) for i in range(n)])
            sag = max(a[2], b[2]) - min(zs)
            wire_rows.append({
                "id": len(wire_rows)+1,
                "id_insulator_start": 0, "id_insulator_end": 0,
                "sag_m": float(sag), "length_m": float(line.length),
                "geometry": line
            })
    gdf_w = gpd.GeoDataFrame(wire_rows, crs=CRS, geometry="geometry")

    out_root.mkdir(parents=True, exist_ok=True)
    gdf_t.to_file(out_root/"tmp_tower.gpkg", layer="tower_axis", driver="GPKG")
    gdf_i.to_file(out_root/"tmp_insulator.gpkg", layer="insulator", driver="GPKG")
    gdf_w.to_file(out_root/"tmp_wire.gpkg", layer="wire", driver="GPKG")
    print("Reconstruction OK (intermediate GPKGs written).")

if __name__=="__main__":
    main()
