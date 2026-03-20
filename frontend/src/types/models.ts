export interface BiasConfig {
  type: string
  strength: 'LOW' | 'MODERATE' | 'HIGH'
  description: string
}

export interface Persona {
  id: string
  name: string
  creator_id: string
  forked_from: string | null
  visibility: 'public' | 'private'
  summary: string
  identity_anchor: string
  epistemic_style: string
  cognitive_biases: BiasConfig[]
  argumentative_voice: string
  opinion_change_threshold: 'LOW' | 'MODERATE' | 'HIGH'
  tags: string[]
  avatar_emoji: string
  times_used: number
  effectiveness_score: number
}

export interface UserReasoningProfile {
  sessions_count: number
  most_engaged_tags: string[]
  least_engaged_tags: string[]
  personas_favorited: string[]
  ignored_perspective_types: string[]
  override_frequency: number
  avg_rounds_before_ending: number
  position_change_rate: number
}

export interface DecisionFrame {
  focus: string
  constraints: string[]
  stakeholders: string[]
  unknowns: string[]
}

export interface UploadedDocument {
  id: string
  filename: string
  mime_type: string
  size_bytes: number
  extraction_status: 'ready' | 'failed'
  extracted_text_preview: string
  extracted_char_count: number
  created_at: string
}

export interface PersonaStance {
  persona_id: string
  persona_name: string
  avatar_emoji: string
  stance: number
  confidence: number
  label: 'for' | 'against' | 'undecided'
  rationale: string
}

export interface PanelRecommendation {
  persona: Persona
  reasons: string[]
  initial_stance: PersonaStance
}

export interface PanelRecommendationResponse {
  decision_frame: DecisionFrame
  blind_spot_message: string
  recommendations: PanelRecommendation[]
  suggested_ids: string[]
  selection_source: 'anthropic' | 'fallback'
  selection_notice: string | null
}

export interface CreatePersonaPayload {
  name: string
  summary: string
  identity_anchor: string
  epistemic_style: string
  argumentative_voice: string
  tags: string[]
  opinion_change_threshold: 'LOW' | 'MODERATE' | 'HIGH'
  avatar_emoji: string
  visibility: 'public' | 'private'
  creator_id: string
  cognitive_biases: BiasConfig[]
}

export interface Message {
  id: string
  author_id: string
  author_name: string
  avatar_emoji: string
  role: 'persona' | 'user' | 'system'
  round_index: number
  content: string
  stance: number | null
  confidence: number | null
  cue: string | null
  timestamp: string
}

export interface TrajectoryPoint {
  round_index: number
  stance: number
  confidence: number
}

export interface TrajectorySeries {
  persona_id: string
  persona_name: string
  avatar_emoji: string
  points: TrajectoryPoint[]
}

export interface NetworkEdge {
  source_id: string
  target_id: string
}

export interface ArgumentHighlight {
  persona_name: string
  title: string
  explanation: string
}

export interface DecisionBrief {
  headline: string
  landscape_summary: string
  strongest_arguments: ArgumentHighlight[]
  key_uncertainties: string[]
  blind_spots: string[]
  suggested_next_steps: string[]
}

export interface SessionSnapshot {
  session_id: string
  decision: string
  current_round: number
  round_goal: number
  status: 'idle' | 'running' | 'complete'
  messages: Message[]
  roster: PersonaStance[]
  trajectories: TrajectorySeries[]
  network_edges: NetworkEdge[]
  brief: DecisionBrief | null
}

export interface FlowDraft {
  prompt: string
  documents: UploadedDocument[]
  selectedPersonaIds: string[]
  recommendation: PanelRecommendationResponse | null
  recommendationSeedKey: string | null
  activeSessionId: string | null
}
