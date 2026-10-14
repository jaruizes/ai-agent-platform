import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import { FormsModule } from '@angular/forms';
import type { AppComponent } from '../../app.component';

@Component({
  selector: 'app-resources-form',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './resources-form.component.html',
  styles: [':host { display: contents; }'],
})
export class ResourcesFormComponent { @Input({ required: true }) host!: AppComponent; }
