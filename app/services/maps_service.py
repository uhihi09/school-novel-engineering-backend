import numpy as np
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from app.repositories.report_repository import report_repository
from app.services.gemini_service import gemini_service

class MapsService:
    def get_local_grid_geojson(
        self, db: Session, *, ne_lat: float, ne_lng: float, sw_lat: float, sw_lng: float, zoom: int, dimension: str
    ) -> Dict[str, Any]:
        """F-1: Divides coordinates bounding box into a 3D GeoJSON extrusion grid layer."""
        features = []
        
        # Determine grid size based on zoom and bounding box bounds
        grid_count = 5  # Standard 5x5 grid resolution for clean rendering
        lats = np.linspace(sw_lat, ne_lat, grid_count + 1)
        lngs = np.linspace(sw_lng, ne_lng, grid_count + 1)
        
        # Retrieve crowdsourced reports within these bounds to adjust local scores dynamically
        reports = report_repository.get_by_bounds(db, ne_lat=ne_lat, ne_lng=ne_lng, sw_lat=sw_lat, sw_lng=sw_lng)
        
        for i in range(grid_count):
            for j in range(grid_count):
                grid_sw_lat = lats[i]
                grid_ne_lat = lats[i+1]
                grid_sw_lng = lngs[j]
                grid_ne_lng = lngs[j+1]
                
                # Base seed calculation based on coordinate hashes to keep maps stable and reproducible
                hash_seed = int((grid_sw_lat * 1000 + grid_sw_lng * 1000) % 100)
                
                # Dynamic scoring based on dimension requested
                if dimension == "income":
                    index_val = 40.0 + (hash_seed % 35)
                    grade = "B (Moderate)" if index_val > 60 else "C (Low Distribution)"
                    avg_income = int(2400000 + (hash_seed * 23000))
                    extra_props = {"average_income": avg_income}
                elif dimension == "healthcare":
                    index_val = 25.0 + (hash_seed % 50)
                    grade = "A (High Access)" if index_val > 65 else "D (Extreme Gap)"
                    extra_props = {"doctor_count_per_10k": round(0.5 + (hash_seed * 0.05), 2)}
                elif dimension == "climate":
                    index_val = 30.0 + (hash_seed % 45)
                    grade = "B (Good Air)" if index_val > 55 else "C (Air Hazard)"
                    extra_props = {"pm25_micrograms": round(12.0 + (hash_seed * 0.4), 1)}
                else:  # Education
                    index_val = 50.0 + (hash_seed % 30)
                    grade = "A (Rich Resources)" if index_val > 70 else "B (Average)"
                    extra_props = {"school_count_per_10k": int(1 + (hash_seed % 5))}
                
                # Adjust grid scores based on real crowdsourced reports in that specific grid cell
                grid_reports = [
                    r for r in reports 
                    if grid_sw_lat <= r.Latitude <= grid_ne_lat and grid_sw_lng <= r.Longitude <= grid_ne_lng
                ]
                if grid_reports:
                    # Penalize Gini/equity scores based on validated reports (e.g. accessibility barriers)
                    validated_count = sum(1 for r in grid_reports if r.IsValid)
                    index_val = max(10.0, index_val - (validated_count * 8.5))
                    grade = f"{grade} - Penalized by {validated_count} active reports"
                
                # Create a square polygon feature
                polygon_coords = [
                    [grid_sw_lng, grid_sw_lat],
                    [grid_ne_lng, grid_sw_lat],
                    [grid_ne_lng, grid_ne_lat],
                    [grid_sw_lng, grid_ne_lat],
                    [grid_sw_lng, grid_sw_lat]
                ]
                
                grid_id = f"grid_{hash_seed}_{i}_{j}"
                features.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [polygon_coords]
                    },
                    "properties": {
                        "grid_id": grid_id,
                        "index_value": round(index_val, 1),
                        "grade": grade,
                        **extra_props
                    }
                })
                
        return {
            "type": "FeatureCollection",
            "dimension": dimension,
            "features": features
        }

    def get_satellite_poverty_index(
        self, *, lat: float, lng: float, region_name: str
    ) -> Dict[str, Any]:
        """F-4: Returns a Satellite Poverty Index (SPI) report for the target coordinates.

        The overall grade and sub-indicators come from Gemini vision analysis of the region's
        satellite tile; without credentials a deterministic-by-coordinate mock is returned so the
        endpoint stays demoable. A real Earth Engine / GCS tile can be passed through to the vision
        model via gemini_service.analyze_satellite_imagery(image_bytes=...).
        """
        # Stable per-coordinate seed keeps the mock report reproducible for a given location.
        seed = int((abs(lat) * 1000 + abs(lng) * 1000)) % 100
        report = gemini_service.analyze_satellite_imagery(region_name=region_name, seed=seed)
        return {
            "region_name": region_name,
            "latitude": round(lat, 6),
            "longitude": round(lng, 6),
            **report,
        }

maps_service = MapsService()
