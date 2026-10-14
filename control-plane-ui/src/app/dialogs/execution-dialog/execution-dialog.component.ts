import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import { FormsModule } from '@angular/forms';
import type { AppComponent } from '../../app.component';

@Component({
  selector: 'app-execution-dialog',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './execution-dialog.component.html',
  styles: [':host { display: contents; }'],
})
export class ExecutionDialogComponent { @Input({ required: true }) host!: AppComponent; }
