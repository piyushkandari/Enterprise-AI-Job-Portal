// frontend/lib/types.ts
export type Role = "employer" | "candidate";

export interface UserResponse {
  id: string;
  email: string;
  role: Role;
  created_at: string;
}

export interface Job {
  id: string;
  employer_id: string;
  title: string;
  description: string;
  structured_requirements: Record<string, unknown>;
  status: "open" | "closed";
  created_at: string;
}

export interface Resume {
  id: string;
  candidate_id: string;
  raw_text: string;
  structured_profile: Record<string, unknown>;
  embedding_id: string | null;
  uploaded_at: string;
}

export interface Verdict {
  requirement: string;
  status: "met" | "partial" | "missing";
  confidence: number;
  evidence: string;
  weight: number;
}

export interface MatchResult {
  job_id: string;
  resume_id: string;
  score: number;
  explanation: string;
  verdicts: Verdict[];
  trace_id?: string;
  token_usage?: Array<{ node: string; input: number; output: number }>;
  errors?: string[];
}

export interface Recommendation {
  job_id: string;
  job_title: string;
  score: number;
  explanation: string;
  verdicts: Verdict[];
}