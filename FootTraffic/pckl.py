import geopandas as gpd
from shapely.geometry import Point


def get_traffic_by_coords(lat, lon, geojson_path):
    """
    Finds the nearest sidewalk segment to a Lat/Long coordinate
    and returns its calibrated pedestrian traffic estimates.
    """
    # 1. Load the GeoJSON file
    print("Loading NYC Pedestrian Network data...")
    gdf = gpd.read_file(geojson_path)

    # 2. Create a point from the Lat/Long (WGS84 - EPSG:4326)
    # Note: Longitude comes first in Point(x, y)
    user_point = Point(lon, lat)

    # 3. Put point into a GeoDataFrame and convert to the file's CRS (EPSG:6538)
    # This ensures distance is calculated in meters, not degrees.
    point_gdf = gpd.GeoDataFrame(
        geometry=[user_point],
        crs="EPSG:4326"
    ).to_crs(gdf.crs)

    # 4. Find the nearest sidewalk segment within 30 meters
    print(f"Searching for sidewalks near {lat}, {lon}...")
    nearest = gpd.sjoin_nearest(
        point_gdf,
        gdf,
        max_distance=30,
        distance_col="dist_meters"
    )

    if nearest.empty:
        return "No sidewalk segments found within 30 meters of these coordinates."

    # 5. Define only the calibrated estimate columns
    output_cols = [
        '__GUID',  # Segment ID
        'predwkdyAM',  # Weekday 8-9AM
        'predwkdyMD',  # Weekday 12:30-1:30PM
        'predwkdyPM',  # Weekday 5-6PM
        'predwkndAM',  # Weekend 8-9AM
        'predwkndMD',  # Weekend 12:30-1:30PM
        'predwkndPM',  # Weekend 5-6PM
        'dist_meters'  # How far the sidewalk is from your point
    ]

    return nearest[output_cols]


# --- Usage ---
# Example: Coordinates for the corner of 5th Ave & 42nd St
my_lat, my_lon = 40.7254116,-73.9919009
file_name = 'NYC_pednetwork_estimates_counts_2018-2019.geojson'

result = get_traffic_by_coords(my_lat, my_lon, file_name)

# Display the results
print(result.to_string(index=False))