---
name: python-geodata
description: >
  [STATUS: confirmed] [CONFIDENCE: high] [VALIDATED: 2026-03-12]
  Python geodata engineering: rasterio, geopandas, shapely, pyproj, CRS transforms.
  Triggers: rasterio, geopandas, shapely, CRS, spatial join, растр, вектор, геоданные.
---

# SKILL: Python Geodata Engineering
# Domain: Geospatial Python | Level: Applied | Version: 1.0
# Scope: Global (применим ко всем гео-проектам)

## Когда загружать этот skill
- Работа с rasterio, geopandas, shapely, pyproj
- CRS трансформации и проекции
- Spatial joins и proximity queries
- Performance optimization для больших растров

## Proven Stack (из patterns.md)
| Задача | Библиотека | Почему |
|--------|-----------|--------|
| Растры (TIF, satellite) | rasterio | Window API, CRS-aware, lazy read |
| Вектора (points, polygons) | geopandas + shapely | Pandas-like API, spatial joins |
| CRS трансформации | pyproj | EPSG support, batch transform |
| Spatial index | shapely.STRtree | R-tree, O(log N) lookup |
| Clustering | sklearn.DBSCAN | Пространственная кластеризация |
| Visualization | folium | Interactive maps, no GUI needed |
| ML for geo | scikit-learn | RandomForest, IsolationForest |

## Performance Patterns (проверено на GeoScan)

### 1. Window reads (не загружай весь растр!)
```python
# BAD: 460MB в RAM per band
data = src.read(1)

# GOOD: только bbox зоны + buffer
from rasterio.windows import from_bounds
window = from_bounds(xmin - 500, ymin - 500, xmax + 500, ymax + 500, src.transform)
data = src.read(1, window=window)  # ~1MB
```
**Результат:** 100x speedup (50 мин → 30 сек per zone)

### 2. STRtree для point-in-polygon (не nested loops!)
```python
# BAD: O(N*M) — 505 zones * 1.2M points = freeze
for zone in zones:
    for point in points:
        if zone.contains(point): ...

# GOOD: O(N*log(M)) через spatial index
from shapely import STRtree
tree = STRtree(points)
for zone in zones:
    candidates = tree.query(zone.geometry)  # bbox pre-filter
    hits = [p for p in candidates if zone.geometry.contains(p)]
```
**Результат:** из зависания → секунды

### 3. Vectorized numpy (не python loops!)
```python
# BAD: numpy в цикле = O(N*M)
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
**Результат:** зависание → 11 сек

### 4. Batch CRS transform
```python
# BAD: 52K вызовов по 1 точке
for x, y in points:
    lon, lat = rasterio.warp.transform(src_crs, dst_crs, [x], [y])

# GOOD: один batch-вызов
xs, ys = zip(*points)
lons, lats = rasterio.warp.transform(src_crs, dst_crs, list(xs), list(ys))
```

### 5. IsolationForest subsampling
```python
# BAD: fit на 125M точек = 90 мин
clf = IsolationForest()
clf.fit(all_data)

# GOOD: subsampling = same quality, 10x faster
clf = IsolationForest(max_samples="auto")  # 256 per tree
sample_idx = np.random.choice(len(all_data), 500_000, replace=False)
clf.fit(all_data[sample_idx])
scores = clf.decision_function(all_data)  # score всех
```
**Результат:** 107 мин → 10.6 мин, качество не изменилось

## CRS Quick Reference
| EPSG | Название | Когда использовать |
|------|----------|-------------------|
| 4326 | WGS 84 (lon/lat) | Хранение, визуализация, Neo4j |
| 32642 | UTM 42N | Казахстан восток (Bestobe) — для метрических расчётов |
| 32643 | UTM 43N | Казахстан запад — для метрических расчётов |
| 3857 | Web Mercator | Только для web-карт (Folium), НИКОГДА для расчётов! |

**Правило:** Хранить в 4326, считать в UTM, показывать в 4326 или 3857.

## Safe Division Pattern (для всех индексов)
```python
def safe_ratio(a: np.ndarray, b: np.ndarray, fill: float = 0.0) -> np.ndarray:
    """Division без NaN/Inf. Используй для ВСЕХ spectral indices."""
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

# Buffer в метрах (нужен UTM!)
gdf_utm = gdf.to_crs(epsg=32642)
gdf_utm["buffer"] = gdf_utm.geometry.buffer(5000)  # 5km

# Distance matrix (в метрах)
from shapely.ops import nearest_points
# Для больших наборов — STRtree, не brute force
```
