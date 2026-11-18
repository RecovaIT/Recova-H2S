import type { SyntheticPatientCase, DeterministicScoreOutput } from '@/types/recova';
export function generateMalaffiFhirBundle(_opts: {
  patientCase: SyntheticPatientCase;
  scoringResult: DeterministicScoreOutput;
  clinicianSignedOff: boolean;
}) {
  return { resourceType: 'Bundle', type: 'transaction', entry: [] };
}