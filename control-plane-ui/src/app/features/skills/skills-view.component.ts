import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import { FormsModule } from '@angular/forms';
import type { AppComponent } from '../../app.component';

@Component({
  selector: 'app-skills-view',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './skills-view.component.html',
  styles: [':host { display: contents; }'],
})
export class SkillsViewComponent { @Input({ required: true }) host!: AppComponent; }
