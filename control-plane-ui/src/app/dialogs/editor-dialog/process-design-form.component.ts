import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import { FormsModule } from '@angular/forms';
import type { AppComponent } from '../../app.component';

@Component({
  selector: 'app-process-design-form',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './process-design-form.component.html',
  styles: [':host { display: contents; }'],
})
export class ProcessDesignFormComponent { @Input({ required: true }) host!: AppComponent; }
