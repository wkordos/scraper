import { AfterViewInit, Component, OnDestroy } from '@angular/core';
import * as L from 'leaflet';
import { Subject, of } from 'rxjs';
import { catchError, debounceTime, distinctUntilChanged, map, switchMap, takeUntil } from 'rxjs/operators';
import { PropertyService, GeoJsonFeatureCollection } from '../../services/property';

@Component({
  selector: 'app-map',
  templateUrl: './map.html',
  styleUrls: ['./map.css'],
})
export class Map implements AfterViewInit, OnDestroy {
  private map?: L.Map;

  // warstwa na nieruchomości (GeoJSON)
  private propertiesLayer?: L.GeoJSON;

  // trigger do przeładowywania danych (bbox/zoom)
  private refresh$ = new Subject<void>();
  private destroy$ = new Subject<void>();

 constructor(private propertyService: PropertyService) {}


  ngAfterViewInit(): void {
    // Start w Warszawie
    this.map = L.map('map', {
      center: [52.2297, 21.0122],
      zoom: 12,
    });



    const osm = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 });
    osm.addTo(this.map);

    const kiegUrl = 'https://integracja.gugik.gov.pl/cgi-bin/KrajowaIntegracjaEwidencjiGruntow?language=pol&';
    const dzialki = L.tileLayer.wms(kiegUrl, {
      layers: 'dzialki',
      format: 'image/png',
      transparent: true,
      version: '1.3.0',
    });

    dzialki.addTo(this.map);

    // (opcjonalnie) kontrolka warstw
    L.control.layers({ OSM: osm }, { 'Działki (WMS)': dzialki }).addTo(this.map);

// utwórz warstwę na dane z backendu
    this.propertiesLayer = L.geoJSON(undefined, {
      // styl dla poligonów/line (opcjonalnie)
      // style: () => ({ weight: 2 }),
      onEachFeature: (feature, layer) => {
        // popup (opcjonalnie)
        const props = feature.properties || {};
        if (props['id'] !== undefined) {
          layer.bindPopup(`ID: ${props['id']}`);
        }
      },
      pointToLayer: (feature, latlng) => {
        // jeśli backend zwraca punkty (np. centroidy)
        return L.circleMarker(latlng);
      },
    }).addTo(this.map);

    // RX pipeline: po refresh pobierz bbox+zoom → call API → wstaw do warstwy
    this.refresh$
      .pipe(
        debounceTime(250),
        map(() => this.getMapViewKey()),
        distinctUntilChanged((a, b) => a.key === b.key),
        switchMap((view) =>
          this.propertyService.getPropertiesByBbox(view.bbox, view.zoom).pipe(
            catchError((err) => {
              console.error('Failed to load properties', err);
              // zostaw poprzednie dane lub wyczyść – tu zostawiamy poprzednie i zwracamy pusty zbiór
              return of({ type: 'FeatureCollection', features: [] } as GeoJsonFeatureCollection);
            })
          )
        ),
        takeUntil(this.destroy$)
      )
      .subscribe((geojson) => {
        if (!this.propertiesLayer) return;
        this.propertiesLayer.clearLayers();
        this.propertiesLayer.addData(geojson as any);
      });

    // odświeżanie przy przesuwaniu i zoomie
    this.map.on('moveend', () => this.refresh$.next());
    this.map.on('zoomend', () => this.refresh$.next());

    // pierwszy load
    this.refresh$.next();


  }

  ngOnDestroy(): void {
    this.map?.remove();
  }

private getMapViewKey(): { bbox: [number, number, number, number]; zoom: number; key: string } {
    if (!this.map) {
      // fallback (nie powinno się zdarzyć po init)
      return { bbox: [0, 0, 0, 0], zoom: 0, key: '0' };
    }

    const b = this.map.getBounds();
    const zoom = this.map.getZoom();

    const bbox: [number, number, number, number] = [
      b.getWest(),
      b.getSouth(),
      b.getEast(),
      b.getNorth(),
    ];

    // key do distinctUntilChanged: zaokrąglamy, żeby nie strzelać requestem przy minimalnych różnicach
    const key = `${zoom}:${bbox.map((v) => v.toFixed(5)).join(',')}`;

    return { bbox, zoom, key };
  }


} 
