import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import { FormsModule } from '@angular/forms';
import type { AppComponent } from '../../app.component';

@Component({
  selector: 'app-governance-form',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './governance-form.component.html',
  styles: [':host { display: contents; }'],
})
export class GovernanceFormComponent { @Input({ required: true }) host!: AppComponent; }
