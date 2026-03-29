import os
import geopandas as gpd
from shapely.geometry import Point

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_GEOJSON = os.path.join(
    PROJECT_ROOT, os.pardir, "data",
    "NYC_pednetwork_estimates_counts_2018-2019.geojson",
)


def get_traffic_by_coords(lat, lon, geojson_path=None):
    """
    Finds the nearest sidewalk segment to a Lat/Long coordinate
    and returns its calibrated pedestrian traffic estimates.
    """
    if geojson_path is None:
        geojson_path = DEFAULT_GEOJSON

    gdf = gpd.read_file(geojson_path)

    user_point = Point(lon, lat)

    point_gdf = gpd.GeoDataFrame(
        geometry=[user_point],
        crs="EPSG:4326"
    ).to_crs(gdf.crs)

    nearest = gpd.sjoin_nearest(
        point_gdf,
        gdf,
        max_distance=30,
        distance_col="dist_meters"
    )

    if nearest.empty:
        return "No sidewalk segments found within 30 meters of these coordinates."

    output_cols = [
        '__GUID',
        'predwkdyAM',
        'predwkdyMD',
        'predwkdyPM',
        'predwkndAM',
        'predwkndMD',
        'predwkndPM',
        'dist_meters',
    ]

    return nearest[output_cols]


if __name__ == "__main__":
    my_lat, my_lon = 40.7254116, -73.9919009
    result = get_traffic_by_coords(my_lat, my_lon)
    print(result.to_string(index=False))
