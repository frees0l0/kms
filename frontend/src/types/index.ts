// API Types

export interface LoginRequest {
  username: string
  password: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
}

export interface DocumentResponse {
  id: number
  name: string
  format: string
  size_bytes: number
  upload_time: string
  status: 'pending' | 'processed' | 'error'
  intent_space_id: number | null
  intent_space_name: string | null
  error_message: string | null
}

export interface DocumentListResponse {
  total: number
  page: number
  page_size: number
  items: DocumentResponse[]
}

export interface IntentSpaceResponse {
  id: number
  name: string
  description: string | null
  keywords: string | null
  document_count: number
  accuracy: number | null
}

export interface IntentSpaceListResponse {
  data: IntentSpaceResponse[]
}

export interface IntentSpaceCreate {
  name: string
  description?: string
  keywords?: string
}

export interface IntegrationResponse {
  channel: string
  is_active: boolean
  last_test_at: string | null
  config_hint: string
}

export interface IntegrationListResponse {
  data: IntegrationResponse[]
}

export interface DashboardSummary {
  frontend_integrations: IntegrationResponse[]
  kb_stats: {
    total_documents: number
    processed: number
    pending: number
    error: number
  }
  intent_spaces: Array<{
    id: number
    name: string
    document_count: number
  }>
  analytics: {
    total_queries: number
  }
}

export interface AnalyticsStats {
  total_queries: number
  avg_response_time_ms: number
  avg_accuracy: number | null
}

export interface IntentDistribution {
  intent: string
  count: number
}

export interface IntentDistributionResponse {
  distribution: IntentDistribution[]
}

export interface TopDocument {
  id: number
  name: string
  hit_count: number
  intent_space: string | null
}

export interface TopDocumentsResponse {
  documents: TopDocument[]
}

export interface QueryLog {
  id: number
  timestamp: string
  source: string
  user_id: string
  query_text: string
  intent: string | null
  intent_id: number | null
  confidence: number | null
  response_time_ms: number | null
  user_feedback: string | null
  corrected_intent_id: number | null
}

export interface QueryLogResponse {
  total: number
  page: number
  page_size: number
  items: QueryLog[]
}
