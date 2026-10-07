from pathlib import Path
import tempfile
import zipfile

import geopandas as gpd
from pyproj import CRS
from shapely.geometry import mapping


SUPPORTED_MEASUREMENT_TYPES = {"Polygon", "MultiPolygon", "LineString", "MultiLineString"}


def _find_shapefile(directory: Path) -> Path:
    shp_files = list(directory.rglob("*.shp"))
    if not shp_files:
        raise ValueError("ZIP archive does not contain a .shp Shapefile.")
    if len(shp_files) > 1:
        raise ValueError("ZIP archive must contain exactly one Shapefile dataset.")
    return shp_files[0]


def _select_metric_crs(gdf: gpd.GeoDataFrame) -> CRS:
    if gdf.crs is None:
        raise ValueError("Input file has no CRS. A CRS is required for safe measurement.")

    source = CRS.from_user_input(gdf.crs)
    if not source.is_geographic:
        return source

    # GeoPandas/pyproj choose an appropriate UTM zone for the dataset centroid.
    estimated = gdf.estimate_utm_crs()
    if estimated is None:
        raise ValueError("Could not determine a suitable projected CRS for measurement.")
    return CRS.from_user_input(estimated)


def _geometry_to_json(geometry):
    if geometry is None or geometry.is_empty:
        return None
    return mapping(geometry)


def process_geospatial_file(source_path: Path) -> dict:
    source_type = source_path.suffix.lower().lstrip(".")
    if source_type == "kml":
        gdf = gpd.read_file(source_path, driver="KML")
    elif source_type == "zip":
        with tempfile.TemporaryDirectory() as tmp:
            with zipfile.ZipFile(source_path) as archive:
                bad_member = next(
                    (
                        m for m in archive.infolist()
                        if Path(m.filename).is_absolute()
                        or ".." in Path(m.filename).parts
                    ),
                    None,
                )
                if bad_member:
                    raise ValueError("ZIP contains an unsafe path.")
                archive.extractall(tmp)
            shp = _find_shapefile(Path(tmp))
            gdf = gpd.read_file(shp)
        source_type = "shapefile"
    else:
        raise ValueError("Unsupported source.")

    if gdf.empty:
        return {
            "feature_count": 0,
            "crs": str(gdf.crs) if gdf.crs else "UNKNOWN",
            "source_type": source_type,
            "features": [],
        }

    if gdf.crs is None:
        raise ValueError("Input file has no CRS. Please provide a file with a defined CRS.")

    source_crs = CRS.from_user_input(gdf.crs)
    metric_crs = _select_metric_crs(gdf)
    measured_gdf = gdf.to_crs(metric_crs)

    features = []
    for idx, (row, measured_geometry) in enumerate(zip(gdf.itertuples(index=False), measured_gdf.geometry)):
        original_geometry = gdf.geometry.iloc[idx]
        geometry_type = original_geometry.geom_type if original_geometry is not None else "Unknown"

        measurement = None
        measurement_unit = None
        if measured_geometry is not None and not measured_geometry.is_empty:
            if geometry_type in {"Polygon", "MultiPolygon"}:
                measurement = float(measured_geometry.area)
                measurement_unit = "square_meters"
            elif geometry_type in {"LineString", "MultiLineString"}:
                measurement = float(measured_geometry.length)
                measurement_unit = "meters"

        properties = {}
        for column in gdf.columns:
            if column != gdf.geometry.name:
                value = getattr(row, column)
                # Convert common NumPy scalar values to native Python values.
                try:
                    value = value.item()
                except AttributeError:
                    pass
                if value is not None:
                    properties[column] = value

        features.append(
            {
                "feature_id": idx,
                "geometry_type": geometry_type,
                "geometry": _geometry_to_json(original_geometry),
                "crs": f"EPSG:{source_crs.to_epsg()}" if source_crs.to_epsg() else source_crs.to_string(),
                "properties": properties,
                "measurement": {
                    "value": measurement,
                    "unit": measurement_unit,
                    "calculation_crs": metric_crs.to_string() if measurement is not None else None,
                },
            }
        )

    return {
        "feature_count": len(features),
        "crs": f"EPSG:{source_crs.to_epsg()}" if source_crs.to_epsg() else source_crs.to_string(),
        "source_type": source_type,
        "features": features,
    }
