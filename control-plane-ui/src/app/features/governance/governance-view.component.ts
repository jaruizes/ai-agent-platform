import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import { FormsModule } from '@angular/forms';
import type { AppComponent } from '../../app.component';

@Component({
  selector: 'app-governance-view',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './governance-view.component.html',
  styles: [':host { display: contents; }'],
})
export class GovernanceViewComponent { @Input({ required: true }) host!: AppComponent; }
