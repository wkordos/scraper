import { AfterViewInit, Component, OnDestroy } from '@angular/core';
import * as L from 'leaflet';

@Component({
  selector: 'app-map',
  templateUrl: './map.html',
  styleUrls: ['./map.css'],
})
export class Map implements AfterViewInit, OnDestroy {
  private map?: L.Map;

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
  }

  ngOnDestroy(): void {
    this.map?.remove();
  }
}
