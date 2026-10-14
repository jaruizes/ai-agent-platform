import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import { FormsModule } from '@angular/forms';
import type { AppComponent } from '../../app.component';

@Component({
  selector: 'app-knowledge-view',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './knowledge-view.component.html',
  styles: [':host { display: contents; }'],
})
export class KnowledgeViewComponent { @Input({ required: true }) host!: AppComponent; }
