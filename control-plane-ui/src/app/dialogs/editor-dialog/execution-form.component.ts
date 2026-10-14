import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import { FormsModule } from '@angular/forms';
import type { AppComponent } from '../../app.component';

@Component({
  selector: 'app-execution-form',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './execution-form.component.html',
  styles: [':host { display: contents; }'],
})
export class ExecutionFormComponent { @Input({ required: true }) host!: AppComponent; }
