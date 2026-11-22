import type { ProfileKey } from './profile';

export type FieldKind = 'text' | 'textarea' | 'select' | 'radio' | 'checkbox' | 'file' | 'custom';
export type FieldStatus = 'ready' | 'manual' | 'sensitive' | 'already-filled' | 'unsupported';
export type AdapterId = 'generic' | 'greenhouse' | 'lever';
export type IssueSeverity = 'warning' | 'needs-review' | 'error' | 'unsupported';

export interface ValidationIssue {
  code: 'required_missing' | 'invalid_value' | 'website_error' | 'sensitive_review' | 'manual_control' | 'cross_origin_frame' | 'unverified_fill';
  severity: IssueSeverity;
  label: string;
  fieldIndex?: number;
  message: string;
  suggestion: string;
}

export interface FormField {
  index: number;
  label: string;
  kind: FieldKind;
  required: boolean;
  options?: string[];
  status: FieldStatus;
}

export interface FillPlanItem {
  index: number;
  label: string;
  kind: FieldKind;
  profileKey: ProfileKey;
  value: string;
}

export interface FillResult {
  index: number;
  label: string;
  status: 'verified' | 'skipped' | 'error';
  reason: string;
}

export type ContentRequest =
  | { type: 'AUTO_FILL_SCAN' }
  | { type: 'AUTO_FILL_APPLY'; adapterId: AdapterId; pageUrl: string; expected: FormField[]; plan: FillPlanItem[] };

export interface FormChangedMessage {
  type: 'AUTO_FILL_CHANGED';
  adapterId: AdapterId;
  pageUrl: string;
  fields: FormField[];
  issues: ValidationIssue[];
}

export type ContentResponse =
  | { ok: true; adapterId: AdapterId; pageUrl: string; fields: FormField[]; issues: ValidationIssue[] }
  | { ok: true; adapterId: AdapterId; pageUrl: string; fields: FormField[]; issues: ValidationIssue[]; results: FillResult[]; formChanged: boolean }
  | { ok: false; error: string };
