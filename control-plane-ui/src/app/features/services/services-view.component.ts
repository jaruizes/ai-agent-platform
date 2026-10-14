import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import { FormsModule } from '@angular/forms';
import type { AppComponent } from '../../app.component';

@Component({
  selector: 'app-services-view',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './services-view.component.html',
  styles: [':host { display: contents; }'],
})
export class ServicesViewComponent { @Input({ required: true }) host!: AppComponent; }
