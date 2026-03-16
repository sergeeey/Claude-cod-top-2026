---
name: python-geodata
description: >
  [STATUS: confirmed] [CONFIDENCE: high] [VALIDATED: 2026-03-12]
  Python geodata engineering: rasterio, geopandas, shapely, pyproj, CRS transforms.
  Triggers: rasterio, geopandas, shapely, CRS, spatial join, raster, vector, geodata, geospatial.
---

# SKILL: Python Geodata Engineering
# Domain: Geospatial Python | Level: Applied | Version: 1.0
# Scope: Global (applicable to all geo projects)

## When to Load This Skill
- Working with rasterio, geopandas, shapely, pyproj
- CRS transformations and projections
- Spatial joins and proximity queries
- Performance optimization for large rasters

## Proven Stack (from patterns.md)
| Task | Library | Why |
|------|---------|-----|
| Rasters (TIF, satellite) | rasterio | Window API, CRS-aware, lazy read |
| Vectors (points, polygons) | geopandas + shapely | Pandas-like API, spatial joins |
| CRS transforms | pyproj | EPSG support, batch transform |
| Spatial index | shapely.STRtree | R-tree, O(log N) lookup |
| Clustering | sklearn.DBSCAN | Spatial clustering |
| Visualization | folium | Interactive maps, no GUI needed |
| ML for geo | scikit-learn | RandomForest, IsolationForest |

## Performance Patterns (verified on GeoScan)

### 1. Window reads (do not load the whole raster!)
```python
# BAD: 460MB in RAM per band
data = src.read(1)

# GOOD: only the zone bbox + buffer
from rasterio.windows import from_bounds
window = from_bounds(xmin - 500, ymin - 500, xmax + 500, ymax + 500, src.transform)
data = src.read(1, window=window)  # ~1MB
```
**Result:** 100x speedup (50 min → 30 sec per zone)

### 2. STRtree for point-in-polygon (no nested loops!)
```python
# BAD: O(N*M) — 505 zones * 1.2M points = freeze
for zone in zones:
    for point in points:
        if zone.contains(point): ...

# GOOD: O(N*log(M)) via spatial index
from shapely import STRtree
tree = STRtree(points)
for zone in zones:
    candidates = tree.query(zone.geometry)  # bbox pre-filter
    hits = [p for p in candidates if zone.geometry.contains(p)]
```
**Result:** from freezing to seconds

### 3. Vectorized numpy (no Python loops!)
```python
# BAD: numpy in loop = O(N*M)
for i in range(len(components)):
    mask = np.where(labels == i)  # O(N) on 120M array!

# GOOD: ndimage.find_objects() = O(1) per component
from scipy import ndimage
slices = ndimage.find_objects(labels)
for i, s in enumerate(slices):
    if s is None: continue
    crop = labels[s]
    mask = np.where(crop == i + 1)  # tiny array
```
**Result:** freezing → 11 sec

### 4. Batch CRS transform
```python
# BAD: 52K calls one point at a time
for x, y in points:
    lon, lat = rasterio.warp.transform(src_crs, dst_crs, [x], [y])

# GOOD: single batch call
xs, ys = zip(*points)
lons, lats = rasterio.warp.transform(src_crs, dst_crs, list(xs), list(ys))
```

### 5. IsolationForest subsampling
```python
# BAD: fit on 125M points = 90 min
clf = IsolationForest()
clf.fit(all_data)

# GOOD: subsampling = same quality, 10x faster
clf = IsolationForest(max_samples="auto")  # 256 per tree
sample_idx = np.random.choice(len(all_data), 500_000, replace=False)
clf.fit(all_data[sample_idx])
scores = clf.decision_function(all_data)  # score all
```
**Result:** 107 min → 10.6 min, quality unchanged

## CRS Quick Reference
| EPSG | Name | When to use |
|------|------|-------------|
| 4326 | WGS 84 (lon/lat) | Storage, visualization, Neo4j |
| 32642 | UTM 42N | East Kazakhstan (Bestobe) — for metric calculations |
| 32643 | UTM 43N | West Kazakhstan — for metric calculations |
| 3857 | Web Mercator | Web maps only (Folium), NEVER for calculations! |

**Rule:** Store in 4326, compute in UTM, display in 4326 or 3857.

## Safe Division Pattern (for all indices)
```python
def safe_ratio(a: np.ndarray, b: np.ndarray, fill: float = 0.0) -> np.ndarray:
    """Division without NaN/Inf. Use for ALL spectral indices."""
    with np.errstate(divide="ignore", invalid="ignore"):
        result = np.where(b != 0, a / b, fill)
    return np.nan_to_num(result, nan=fill, posinf=fill, neginf=fill)
```

## GeoDataFrame Quick Patterns
```python
import geopandas as gpd
from shapely.geometry import Point

# Points → GeoDataFrame
gdf = gpd.GeoDataFrame(
    df, geometry=gpd.points_from_xy(df.lon, df.lat), crs="EPSG:4326"
)

# Spatial join (points in polygons)
result = gpd.sjoin(points_gdf, polygons_gdf, predicate="within")

# Buffer in meters (requires UTM!)
gdf_utm = gdf.to_crs(epsg=32642)
gdf_utm["buffer"] = gdf_utm.geometry.buffer(5000)  # 5km

# Distance matrix (in meters)
from shapely.ops import nearest_points
# For large datasets — STRtree, not brute force
```
