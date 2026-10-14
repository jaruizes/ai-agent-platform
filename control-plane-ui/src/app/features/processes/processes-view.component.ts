import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ControlPlaneViewBase } from '../../shared/control-plane-view.base';

@Component({
  selector: 'app-processes-view',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './processes-view.component.html',
  styles: [':host { display: contents; }'],
})
export class ProcessesViewComponent extends ControlPlaneViewBase {}
