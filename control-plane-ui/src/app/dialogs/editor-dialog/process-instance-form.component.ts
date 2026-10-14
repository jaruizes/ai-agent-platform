import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import { FormsModule } from '@angular/forms';
import type { AppComponent } from '../../app.component';

@Component({
  selector: 'app-process-instance-form',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './process-instance-form.component.html',
  styles: [':host { display: contents; }'],
})
export class ProcessInstanceFormComponent { @Input({ required: true }) host!: AppComponent; }
