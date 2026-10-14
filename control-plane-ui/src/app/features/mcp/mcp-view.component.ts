import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import { FormsModule } from '@angular/forms';
import type { AppComponent } from '../../app.component';

@Component({
  selector: 'app-mcp-view',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './mcp-view.component.html',
  styles: [':host { display: contents; }'],
})
export class McpViewComponent { @Input({ required: true }) host!: AppComponent; }
