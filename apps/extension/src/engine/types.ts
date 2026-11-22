import type { ProfileKey } from './profile';

export type FieldKind = 'text' | 'textarea' | 'select' | 'radio' | 'checkbox' | 'file';
export type FieldStatus = 'ready' | 'manual' | 'sensitive' | 'already-filled' | 'unsupported';

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
  | { type: 'AUTO_FILL_APPLY'; expected: FormField[]; plan: FillPlanItem[] };

export type ContentResponse =
  | { ok: true; fields: FormField[] }
  | { ok: true; results: FillResult[] }
  | { ok: false; error: string };
