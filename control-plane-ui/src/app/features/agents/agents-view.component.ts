import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import { FormsModule } from '@angular/forms';
import type { AppComponent } from '../../app.component';

@Component({
  selector: 'app-agents-view',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './agents-view.component.html',
  styles: [':host { display: contents; }'],
})
export class AgentsViewComponent { @Input({ required: true }) host!: AppComponent; }
