import numpy as np
from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session
from app.db.models import RegionStat
from app.repositories.report_repository import report_repository
from app.services.gemini_service import gemini_service


class MapsService:
    @staticmethod
    def _metric(region: RegionStat, dimension: str):
        return {
            "income": region.AvgIncomeManwon,
            "healthcare": region.DoctorsPer1k,
            "climate": region.Pm25,
            "education": region.EducationIndex,
        }.get(dimension, region.EducationIndex)

    @staticmethod
    def _grade(index_val: float) -> str:
        if index_val >= 75:
            return "A (우수)"
        if index_val >= 55:
            return "B (양호)"
        if index_val >= 35:
            return "C (취약)"
        return "D (심각)"

    @staticmethod
    def _synthetic_cell(dimension: str, seed: int) -> Tuple[float, Dict[str, Any]]:
        """Fallback used ONLY when region_stats is unseeded (flagged via data_source)."""
        if dimension == "income":
            return 40.0 + (seed % 35), {"average_income": int(2400000 + seed * 23000)}
        if dimension == "healthcare":
            return 25.0 + (seed % 50), {"doctor_count_per_10k": round(0.5 + seed * 0.05, 2)}
        if dimension == "climate":
            return 30.0 + (seed % 45), {"pm25_micrograms": round(12.0 + seed * 0.4, 1)}
        return 50.0 + (seed % 30), {"education_index": round(50.0 + (seed % 30), 1)}

    def get_local_grid_geojson(
        self, db: Session, *, ne_lat: float, ne_lng: float, sw_lat: float, sw_lng: float, zoom: int, dimension: str
    ) -> Dict[str, Any]:
        """F-1: Bounding box -> 5x5 GeoJSON grid coloured by REAL per-region inequality stats.

        Each cell takes the values of the nearest seeded region (region_stats). If no region data
        has been seeded, a clearly-flagged synthetic fallback is used. Validated citizen reports
        inside a cell penalise its score (real crowdsourcing feedback loop).
        """
        grid_count = 5
        lats = np.linspace(sw_lat, ne_lat, grid_count + 1)
        lngs = np.linspace(sw_lng, ne_lng, grid_count + 1)

        reports = report_repository.get_by_bounds(db, ne_lat=ne_lat, ne_lng=ne_lng, sw_lat=sw_lat, sw_lng=sw_lng)

        regions = db.query(RegionStat).all()
        usable = [r for r in regions if self._metric(r, dimension) is not None]
        data_source = "real-region-stats" if usable else "synthetic-fallback"

        lo = hi = span = 0.0
        if usable:
            vals = [self._metric(r, dimension) for r in usable]
            lo, hi = min(vals), max(vals)
            span = (hi - lo) or 1.0

        features = []
        for i in range(grid_count):
            for j in range(grid_count):
                gs_lat, gn_lat = lats[i], lats[i + 1]
                gs_lng, gn_lng = lngs[j], lngs[j + 1]
                c_lat, c_lng = (gs_lat + gn_lat) / 2, (gs_lng + gn_lng) / 2

                if usable:
                    nearest = min(usable, key=lambda r: (r.CenterLat - c_lat) ** 2 + (r.CenterLng - c_lng) ** 2)
                    raw = self._metric(nearest, dimension)
                    norm = 100.0 * (raw - lo) / span
                    region_name = nearest.RegionName
                    if dimension == "climate":
                        index_val = round(max(5.0, 100.0 - norm), 1)  # lower PM2.5 => better
                        extra_props = {"pm25_micrograms": round(raw, 1)}
                    elif dimension == "income":
                        index_val = round(max(5.0, norm), 1)
                        extra_props = {"average_income": int(raw * 10000)}  # 만원 -> 원
                    elif dimension == "healthcare":
                        index_val = round(max(5.0, norm), 1)
                        extra_props = {"doctor_count_per_10k": round(raw * 10, 2)}
                    else:  # education
                        index_val = round(max(5.0, norm), 1)
                        extra_props = {"education_index": round(raw, 1)}
                else:
                    seed = int((gs_lat * 1000 + gs_lng * 1000) % 100)
                    index_val, extra_props = self._synthetic_cell(dimension, seed)
                    region_name = "—"

                grade = self._grade(index_val)

                grid_reports = [
                    r for r in reports
                    if gs_lat <= r.Latitude <= gn_lat and gs_lng <= r.Longitude <= gn_lng
                ]
                if grid_reports:
                    validated = sum(1 for r in grid_reports if r.IsValid)
                    if validated:
                        index_val = round(max(5.0, index_val - validated * 8.5), 1)
                        grade = f"{grade} · 제보 {validated}건 반영"

                polygon_coords = [
                    [gs_lng, gs_lat], [gn_lng, gs_lat], [gn_lng, gn_lat],
                    [gs_lng, gn_lat], [gs_lng, gs_lat],
                ]
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "Polygon", "coordinates": [polygon_coords]},
                    "properties": {
                        "grid_id": f"grid_{i}_{j}",
                        "region": region_name,
                        "index_value": index_val,
                        "grade": grade,
                        **extra_props,
                    },
                })

        return {
            "type": "FeatureCollection",
            "dimension": dimension,
            "data_source": data_source,
            "features": features,
        }

    def get_satellite_poverty_index(
        self, *, lat: float, lng: float, region_name: str
    ) -> Dict[str, Any]:
        """F-4: Satellite Poverty Index report. Grounded in real web data (or a real satellite tile
        via Gemini Vision when one is supplied)."""
        report = gemini_service.analyze_satellite_imagery(region_name=region_name, lat=lat, lng=lng)
        return {
            "region_name": region_name,
            "latitude": round(lat, 6),
            "longitude": round(lng, 6),
            **report,
        }


maps_service = MapsService()
