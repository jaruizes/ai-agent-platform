import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ControlPlaneViewBase } from '../../shared/control-plane-view.base';

@Component({
  selector: 'app-editor-dialog',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './editor-dialog.component.html',
  styles: [':host { display: contents; }'],
})
export class EditorDialogComponent extends ControlPlaneViewBase {}
