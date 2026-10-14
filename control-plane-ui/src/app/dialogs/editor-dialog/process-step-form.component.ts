import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import { FormsModule } from '@angular/forms';
import type { AppComponent } from '../../app.component';

@Component({
  selector: 'app-process-step-form',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './process-step-form.component.html',
  styles: [':host { display: contents; }'],
})
export class ProcessStepFormComponent { @Input({ required: true }) host!: AppComponent; }
