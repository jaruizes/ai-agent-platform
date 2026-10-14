import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import { FormsModule } from '@angular/forms';
import type { AppComponent } from '../../app.component';

@Component({
  selector: 'app-tools-view',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './tools-view.component.html',
  styles: [':host { display: contents; }'],
})
export class ToolsViewComponent { @Input({ required: true }) host!: AppComponent; }
