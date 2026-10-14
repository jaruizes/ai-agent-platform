import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import { FormsModule } from '@angular/forms';
import type { AppComponent } from '../../app.component';

@Component({
  selector: 'app-evals-form',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './evals-form.component.html',
  styles: [':host { display: contents; }'],
})
export class EvalsFormComponent { @Input({ required: true }) host!: AppComponent; }
