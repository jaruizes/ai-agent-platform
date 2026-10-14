import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import { FormsModule } from '@angular/forms';
import type { AppComponent } from '../../app.component';

@Component({
  selector: 'app-evals-view',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './evals-view.component.html',
  styles: [':host { display: contents; }'],
})
export class EvalsViewComponent { @Input({ required: true }) host!: AppComponent; }
