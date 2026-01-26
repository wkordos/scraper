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

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap contributors',
    }).addTo(this.map);
  }

  ngOnDestroy(): void {
    this.map?.remove();
  }
}
