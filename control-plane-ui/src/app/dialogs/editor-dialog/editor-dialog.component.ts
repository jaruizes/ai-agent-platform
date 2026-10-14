import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import { FormsModule } from '@angular/forms';
import type { AppComponent } from '../../app.component';

@Component({
  selector: 'app-editor-dialog',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './editor-dialog.component.html',
  styles: [':host { display: contents; }'],
})
export class EditorDialogComponent { @Input({ required: true }) host!: AppComponent; }
