import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import { FormsModule } from '@angular/forms';
import type { AppComponent } from '../../app.component';

@Component({
  selector: 'app-processes-view',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './processes-view.component.html',
  styles: [':host { display: contents; }'],
})
export class ProcessesViewComponent { @Input({ required: true }) host!: AppComponent; }
