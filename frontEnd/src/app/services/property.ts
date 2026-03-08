import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

// Minimalne typy GeoJSON (wystarczy do Leafleta)
export type GeoJsonFeatureCollection = GeoJSON.FeatureCollection<
  GeoJSON.Geometry,
  { [key: string]: any }
>;

@Injectable({
  providedIn: 'root',
})
export class PropertyService {
  // Jeśli masz environment, podepnij to stamtąd:
  // private readonly apiBaseUrl = environment.apiBaseUrl;
  private readonly apiBaseUrl = ''; // gdy frontend i backend są na tym samym host/porcie

  constructor(private http: HttpClient) {}

  getPropertiesByBbox(bbox: [number, number, number, number], zoom: number): Observable<GeoJsonFeatureCollection> {
    const [minLon, minLat, maxLon, maxLat] = bbox;

    const params = new HttpParams()
      .set('bbox', `${minLon},${minLat},${maxLon},${maxLat}`)
      .set('zoom', String(zoom));

    return this.http.get<GeoJsonFeatureCollection>(`${this.apiBaseUrl}/api/properties`, { params });
  }
}

export default PropertyService;