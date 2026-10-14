import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import { FormsModule } from '@angular/forms';
import type { AppComponent } from '../../app.component';

@Component({
  selector: 'app-runtime-view',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './runtime-view.component.html',
  styles: [':host { display: contents; }'],
})
export class RuntimeViewComponent { @Input({ required: true }) host!: AppComponent; }
