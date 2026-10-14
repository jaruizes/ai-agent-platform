import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ControlPlaneViewBase } from '../../shared/control-plane-view.base';

@Component({
  selector: 'app-executions-view',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './executions-view.component.html',
  styles: [':host { display: contents; }'],
})
export class ExecutionsViewComponent extends ControlPlaneViewBase {}
