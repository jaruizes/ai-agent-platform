import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import { FormsModule } from '@angular/forms';
import type { AppComponent } from '../../app.component';

@Component({
  selector: 'app-prompts-view',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './prompts-view.component.html',
  styles: [':host { display: contents; }'],
})
export class PromptsViewComponent { @Input({ required: true }) host!: AppComponent; }
