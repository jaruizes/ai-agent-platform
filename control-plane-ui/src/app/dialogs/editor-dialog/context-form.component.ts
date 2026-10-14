import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import { FormsModule } from '@angular/forms';
import type { AppComponent } from '../../app.component';

@Component({
  selector: 'app-context-form',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './context-form.component.html',
  styles: [':host { display: contents; }'],
})
export class ContextFormComponent { @Input({ required: true }) host!: AppComponent; }
