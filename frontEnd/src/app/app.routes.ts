import { Routes } from '@angular/router';
import { LandingPageComponent } from './pages/landing-page/landing-page';
import { Map } from './pages/map/map';


export const routes: Routes = [
  {path: '',component: LandingPageComponent },
  { path: 'mapa', component: Map },
];
