export type DomainTrack =
  | 'relapse-rehab'
  | 'ifhas-screening'
  | 'neuro-brain'
  | 'osh-workforce';

export type RiskTier = 'GREEN' | 'AMBER' | 'RED' | 'EMERGENCY_BYPASS';
export type AgentNodeStatus = 'idle' | 'running' | 'passed' | 'flagged' | 'bypassed';
export type MetricDirection = 'lower_is_bad' | 'higher_is_bad';

export interface PatientConfounders {
  hearingLoss?: boolean;
  visionLoss?: boolean;
  nonNativeLanguage?: boolean;
  lowEducation?: boolean;
}

export interface AgentStepResult {
  agentId: string;
  agentName: string;
  status: AgentNodeStatus;
  timestamp: string;
  payload: Record<string, unknown>;
  message: string;
}

export interface DeterministicScoreOutput {
  baselineMean: number;
  currentObservation: number;
  sampleSd: number;
  adjustedSe: number;
  practiceGainOffset: number;
  zScore: number;      // raw, undirected Z for display
  signedZ: number;     // direction-aware Z used for tier
  riskTier: RiskTier;
  acuteCrisisFlag?: boolean;
  confidenceIndex: number;
  missingStreamFlags: string[];
  metricKey: string;
  confounderMultiplier?: number;
}

export interface SyntheticPatientCase {
  id: string;
  track: DomainTrack;
  caseLabel: string;
  patientName: string;
  age: number;
  gender: string;
  insuranceTier: 'Thiqa' | 'Enhanced' | 'Basic';
  metricKey: string;
  baselineWindow: number[];
  currentObservations: number[];
  confounders?: PatientConfounders;
  missingDataStreams?: string[];
  acuteCrisisFlag?: boolean;
  symptomsText: string;
  expectedTier?: RiskTier;
  expectedSignedZ?: number;
}