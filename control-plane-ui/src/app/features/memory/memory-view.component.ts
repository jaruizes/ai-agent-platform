import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import { FormsModule } from '@angular/forms';
import type { AppComponent } from '../../app.component';

@Component({
  selector: 'app-memory-view',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './memory-view.component.html',
  styles: [':host { display: contents; }'],
})
export class MemoryViewComponent { @Input({ required: true }) host!: AppComponent; }
