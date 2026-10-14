import { ExecutionFormComponent } from './execution-form.component';
import { ContextFormComponent } from './context-form.component';
import { ResourcesFormComponent } from './resources-form.component';
import { ProcessDesignFormComponent } from './process-design-form.component';
import { ProcessStepFormComponent } from './process-step-form.component';
import { ProcessInstanceFormComponent } from './process-instance-form.component';
import { GovernanceFormComponent } from './governance-form.component';
import { EvalsFormComponent } from './evals-form.component';
import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import { FormsModule } from '@angular/forms';
import type { AppComponent } from '../../app.component';

@Component({
  selector: 'app-editor-dialog',
  standalone: true,
  imports: [CommonModule, FormsModule, ExecutionFormComponent, ContextFormComponent, ResourcesFormComponent, ProcessDesignFormComponent, ProcessStepFormComponent, ProcessInstanceFormComponent, GovernanceFormComponent, EvalsFormComponent],
  templateUrl: './editor-dialog.component.html',
  styles: [':host { display: contents; }'],
})
export class EditorDialogComponent { @Input({ required: true }) host!: AppComponent; }
