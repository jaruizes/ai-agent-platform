import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ControlPlaneViewBase } from '../../shared/control-plane-view.base';

@Component({
  selector: 'app-sessions-view',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './sessions-view.component.html',
  styles: [':host { display: contents; }'],
})
export class SessionsViewComponent extends ControlPlaneViewBase {}
