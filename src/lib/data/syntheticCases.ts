import type { SyntheticPatientCase } from '@/types/recova';

export const SYNTHETIC_CASES: SyntheticPatientCase[] = [
  {
    id: 'rehab-case-a',
    track: 'relapse-rehab',
    caseLabel: 'Case A: Stable Recovery',
    patientName: 'Rashid A.',
    age: 34,
    gender: 'Male',
    insuranceTier: 'Thiqa',
    metricKey: 'sleep_hours',
    baselineWindow: [7.5, 7.8, 7.2, 7.6, 7.4],
    currentObservations: [7.4, 7.5, 7.6],
    symptomsText: 'Feeling well, active daily routines maintained.',
    expectedTier: 'GREEN',
  },
  {
    id: 'rehab-case-b',
    track: 'relapse-rehab',
    caseLabel: 'Case B: Pre-Relapse Drift',
    patientName: 'Tariq M.',
    age: 29,
    gender: 'Male',
    insuranceTier: 'Enhanced',
    metricKey: 'sleep_hours',
    baselineWindow: [7.8, 7.5, 7.6, 7.7, 7.4],
    currentObservations: [5.1, 4.8, 4.2],
    symptomsText: 'Increasing anxiety, disrupted sleep, skipped check-ins.',
    expectedTier: 'RED',
  },
];