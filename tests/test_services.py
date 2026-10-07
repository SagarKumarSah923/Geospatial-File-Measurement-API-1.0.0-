import zipfile
from pathlib import Path

import geopandas as gpd
from shapely.geometry import LineString, Polygon

from app.services import process_geospatial_file


def _zip_shapefile(gdf, tmp_path: Path, name: str) -> Path:
    shp_dir = tmp_path / "shp"
    shp_dir.mkdir()
    shp_path = shp_dir / name
    gdf.to_file(shp_path, driver="ESRI Shapefile")

    zip_path = tmp_path / f"{name}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in shp_dir.iterdir():
            archive.write(path, path.name)
    return zip_path


def test_polygon_area_is_calculated_in_square_meters(tmp_path: Path):
    polygon = Polygon([
        (77.5946, 12.9716),
        (77.6046, 12.9716),
        (77.6046, 12.9816),
        (77.5946, 12.9816),
        (77.5946, 12.9716),
    ])
    gdf = gpd.GeoDataFrame({"name": ["test"]}, geometry=[polygon], crs="EPSG:4326")
    path = _zip_shapefile(gdf, tmp_path, "polygon.shp")

    result = process_geospatial_file(path)
    measurement = result["features"][0]["measurement"]

    assert measurement["unit"] == "square_meters"
    assert measurement["value"] > 0
    assert measurement["calculation_crs"].startswith("EPSG:")


def test_linestring_length_is_calculated_in_meters(tmp_path: Path):
    line = LineString([(77.5946, 12.9716), (77.6046, 12.9716)])
    gdf = gpd.GeoDataFrame({"name": ["test"]}, geometry=[line], crs="EPSG:4326")
    path = _zip_shapefile(gdf, tmp_path, "line.shp")

    result = process_geospatial_file(path)
    measurement = result["features"][0]["measurement"]

    assert measurement["unit"] == "meters"
    assert measurement["value"] > 0
