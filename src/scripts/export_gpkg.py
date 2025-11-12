import argparse, yaml
from pathlib import Path
import geopandas as gpd

def load_cfg(p): 
    import yaml; from pathlib import Path
    return yaml.safe_load(Path(p).read_text())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cfg", required=True)
    args = ap.parse_args()
    cfg = load_cfg(args.cfg)
    out_root = Path(cfg["paths"]["out_root"])
    out_file = out_root / cfg["export"]["gpkg_name"]
    if out_file.exists(): out_file.unlink()

    for layer, tmp in [("tower_axis","tmp_tower.gpkg"), ("insulator","tmp_insulator.gpkg"), ("wire","tmp_wire.gpkg")]:
        gdf = gpd.read_file(out_root/tmp, layer=layer)
        gdf.to_file(out_file, layer=layer, driver="GPKG")
    print("Wrote", out_file)

if __name__=="__main__":
    main()
