import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import { FormsModule } from '@angular/forms';
import type { AppComponent } from '../../app.component';

@Component({
  selector: 'app-sessions-view',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './sessions-view.component.html',
  styles: [':host { display: contents; }'],
})
export class SessionsViewComponent { @Input({ required: true }) host!: AppComponent; }
