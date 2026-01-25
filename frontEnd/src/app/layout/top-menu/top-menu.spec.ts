import { ComponentFixture, TestBed } from '@angular/core/testing';

import { TopMenu } from './top-menu';

describe('TopMenu', () => {
  let component: TopMenu;
  let fixture: ComponentFixture<TopMenu>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [TopMenu]
    })
    .compileComponents();

    fixture = TestBed.createComponent(TopMenu);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
