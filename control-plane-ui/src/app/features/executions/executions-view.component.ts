import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import { FormsModule } from '@angular/forms';
import type { AppComponent } from '../../app.component';

@Component({
  selector: 'app-executions-view',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './executions-view.component.html',
  styles: [':host { display: contents; }'],
})
export class ExecutionsViewComponent { @Input({ required: true }) host!: AppComponent; }
