import { authHeaders, clearToken } from "./auth";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...(options.headers ?? {}),
    },
  });

  if (res.status === 401) {
    clearToken();
    window.location.href = "/login";
    throw new Error("Unauthorized");
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(err.detail ?? "Request failed");
  }

  return res.json();
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "POST", body: JSON.stringify(body) }),
  put: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "PUT", body: JSON.stringify(body) }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};

// ── Auth ──────────────────────────────────────────────────────────────────────
export interface LoginResponse {
  access_token: string;
  token_type: string;
  user_id: string;
  email: string;
  full_name?: string;
  role: string;
  tenant_id?: string | null;
}

export function login(email: string, password: string) {
  return api.post<LoginResponse>("/api/v1/auth/login", { email, password });
}

// ── Clients ───────────────────────────────────────────────────────────────────
export interface Client {
  id: string;
  name: string;
  trn: string;
  type: string;
  industry?: string;
  contact_name?: string;
  contact_email?: string;
  contact_phone?: string;
  status: string;
  docs: number;
  lastActivity: string;
  // Tally mapping
  tally_host?: string;
  tally_port?: number;
  tally_company?: string;
  tally_connected?: boolean;
  tally_edu_mode?: boolean;
  tally_last_sync?: string;
  tally_connector_status?: string;
  // legacy compat
  email?: string;
  phone?: string;
  address?: string;
  vatPeriod?: string;
  registrationDate?: string;
  contactPerson?: string;
}

export interface CreateClientPayload {
  name: string;
  trn: string;
  type: string;
  industry?: string;
  contact_name?: string;
  contact_email?: string;
  contact_phone?: string;
}

export interface TallyMappingPayload {
  tally_host: string;
  tally_port: number;
  tally_company: string;
  tally_edu_mode: boolean;
  [key: string]: unknown;
}

export function getClients() {
  return api.get<Client[]>("/api/v1/clients");
}

export function getClientById(id: string) {
  return api.get<Client>(`/api/v1/clients/${id}`);
}

export function createClient(payload: CreateClientPayload) {
  return api.post<Client>("/api/v1/clients", payload);
}

export function updateClient(id: string, payload: Partial<CreateClientPayload>) {
  return api.put<Client>(`/api/v1/clients/${id}`, payload);
}

export function deleteClient(id: string) {
  return api.delete<{ ok: boolean }>(`/api/v1/clients/${id}`);
}

export function updateTallyMapping(id: string, payload: TallyMappingPayload) {
  return api.put<Client>(`/api/v1/clients/${id}/tally-mapping`, payload);
}

export function testTallyConnection(id: string) {
  return api.post<{ connected: boolean; company_list: string[]; error?: string }>(
    `/api/v1/clients/${id}/test-tally-connection`, {}
  );
}

// ── Tally Settings (DB-backed per-client) ─────────────────────────────────────
export interface TallySettings {
  tally_host?: string;
  tally_port?: number;
  tally_company?: string;
  tally_edu_mode?: boolean;
  tally_connector_status?: string;
}

export function getTallySettings(clientId: string) {
  return api.get<TallySettings>(`/api/v1/tally/settings/${clientId}`);
}

export function updateTallySettings(clientId: string, payload: Partial<TallySettings>) {
  return api.patch<TallySettings>(`/api/v1/tally/settings/${clientId}`, payload);
}

// ── Documents ─────────────────────────────────────────────────────────────────
export interface Document {
  id: string;
  name: string;
  file_name?: string;
  client: string;
  client_id?: string;
  type: string;
  document_type?: string;
  status: string;
  confidence: number;
  confidence_score?: number;
  uploaded: string;
  created_at?: string;
}

export function getDocuments(clientId?: string) {
  const qs = clientId ? `?client_id=${clientId}` : "";
  return api.get<Document[]>(`/api/v1/documents${qs}`);
}

export async function getClientDocuments(clientId: string): Promise<Document[]> {
  return api.get<Document[]>(`/api/v1/documents/client/${clientId}`);
}

export async function getClientVouchers(clientId: string): Promise<Voucher[]> {
  return api.get<Voucher[]>(`/api/v1/vouchers/client/${clientId}`);
}

export async function uploadDocument(file: File, clientId?: string): Promise<Document> {
  const formData = new FormData();
  formData.append("file", file);
  if (clientId) formData.append("client_id", clientId);

  const headers = authHeaders();
  const qs = clientId ? `?client_id=${encodeURIComponent(clientId)}` : "";
  const res = await fetch(`${BASE}/api/v1/documents/upload${qs}`, {
    method: "POST",
    headers,
    body: formData,
  });

  if (res.status === 401) {
    clearToken();
    window.location.href = "/login";
    throw new Error("Unauthorized");
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Upload failed" }));
    throw new Error(err.detail ?? "Upload failed");
  }
  return res.json();
}

export async function assignDocumentClient(docId: string, clientId: string | null): Promise<void> {
  await api.patch(`/api/v1/documents/${docId}/assign-client`, { client_id: clientId });
}

// ── Vouchers ──────────────────────────────────────────────────────────────────
export interface LedgerEntry {
  ledger_name: string;
  is_debit: boolean;
  amount: number;
}

export interface Voucher {
  id: string;
  db_id: number;
  client_id: number;
  client: string;
  document_id: number;
  voucher_type: string;
  voucher_date: string;
  party_name: string;
  narration: string;
  amount: number;
  currency: string;
  description: string;
  display_amount: string;
  type: string;
  ledger_entries: LedgerEntry[];
  approved_entries: LedgerEntry[];
  ai_suggested_data: Record<string, unknown>;
  confidence_score: number;
  status: string;
  rejection_reason: string;
  reviewed_by: string;
  reviewed_at: string;
  tally_voucher_no: string;
  tally_posted_at: string;
  created_at: string;
  updated_at: string;
}

export interface CreateVoucherPayload {
  client: string;
  client_id?: number;
  description: string;
  display_amount?: string;
  amount: number;
  voucher_type: string;
  party_name?: string;
  narration?: string;
  voucher_date?: string;
  type?: string;
}

export interface VoucherFilters {
  status?: string;
  client?: string;
  voucher_type?: string;
  client_id?: number;
}

export function getVouchers(filters?: VoucherFilters) {
  const params = new URLSearchParams();
  if (filters?.status) params.set("status", filters.status);
  if (filters?.client) params.set("client", filters.client);
  if (filters?.voucher_type) params.set("voucher_type", filters.voucher_type);
  if (filters?.client_id) params.set("client_id", String(filters.client_id));
  const q = params.toString();
  return api.get<Voucher[]>(`/api/v1/vouchers${q ? `?${q}` : ""}`);
}

export function getVoucherById(id: string) {
  return api.get<Voucher>(`/api/v1/vouchers/${id}`);
}

export function createVoucher(payload: CreateVoucherPayload) {
  return api.post<Voucher>("/api/v1/vouchers", payload);
}

export function approveVoucher(id: string, approvedBy = "ca_admin") {
  return api.post<Voucher>(`/api/v1/vouchers/${id}/approve`, { approved_by: approvedBy, entries: null });
}

export function rejectVoucher(id: string, reason: string) {
  return api.put<Voucher>(`/api/v1/vouchers/${id}/reject`, { reason });
}

export function submitVoucher(id: string) {
  return api.put<Voucher>(`/api/v1/vouchers/${id}/submit`, {});
}

export function updateVoucherEntries(id: string, entries: LedgerEntry[]) {
  return api.post<Voucher>(`/api/v1/vouchers/${id}/update-entries`, { entries });
}

export function postVoucherToTally(id: string) {
  return api.post<{ success: boolean; voucher_no?: string; message: string }>(
    `/api/v1/vouchers/${id}/post-to-tally`, {}
  );
}

export function getVoucherAuditLog(id: string) {
  return api.get<AuditLogEntry[]>(`/api/v1/vouchers/${id}/audit-log`);
}

// ── Review Queue ──────────────────────────────────────────────────────────────
export interface ReviewQueueItem {
  type: "voucher" | "document";
  id: string;
  client: string;
  description: string;
  amount?: string;
  status: string;
  priority: string;
  created_at: string;
}

export interface AuditLogEntry {
  id: number;
  entity_type: string;
  entity_id: string;
  action: string;
  actor: string;
  details: Record<string, unknown>;
  client: string;
  created_at: string;
}

export function getReviewQueue() {
  return api.get<ReviewQueueItem[]>("/api/v1/review-queue");
}

export function getAuditLog() {
  return api.get<AuditLogEntry[]>("/api/v1/review-queue/audit-log");
}

// ── Settings / Users ──────────────────────────────────────────────────────────
export interface AppUser {
  id: number;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

export interface CreateUserPayload {
  email: string;
  full_name: string;
  password: string;
  role: string;
  [key: string]: unknown;
}

export function getUsers() {
  return api.get<AppUser[]>("/api/v1/settings/users");
}

export function createUser(payload: CreateUserPayload) {
  return api.post<AppUser>("/api/v1/settings/users", payload);
}

export function updateUser(id: number, payload: Partial<CreateUserPayload & { is_active: boolean }>) {
  return api.put<AppUser>(`/api/v1/settings/users/${id}`, payload);
}

export function deleteUser(id: number) {
  return api.delete<{ ok: boolean }>(`/api/v1/settings/users/${id}`);
}

// ── Chat ──────────────────────────────────────────────────────────────────────
export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatResponse {
  reply: string;
}

export function sendChatMessage(messages: ChatMessage[]) {
  return api.post<ChatResponse>("/api/v1/chat", { messages });
}

// ── Financial Reports ──────────────────────────────────────────────────────────
export interface ReportEntry {
  ledger: string;
  opening_dr?: number;
  opening_cr?: number;
  transactions_dr?: number;
  transactions_cr?: number;
  closing_dr?: number;
  closing_cr?: number;
  amount?: number;
  name?: string;
}

export interface TrialBalanceGroup {
  name: string;
  entries: ReportEntry[];
}

export interface TrialBalanceReport {
  report_type: "trial_balance";
  period: string;
  generated_at: string;
  demo_mode?: boolean;
  client_id: string;
  client_name: string;
  groups: TrialBalanceGroup[];
  totals: { debit: number; credit: number };
  tally_error?: string;
}

export interface PLReport {
  report_type: "profit_loss";
  period: string;
  generated_at: string;
  demo_mode?: boolean;
  client_id: string;
  client_name: string;
  income: { name: string; amount: number }[];
  expenses: { name: string; amount: number }[];
  total_income: number;
  total_expenses: number;
  gross_profit: number;
  net_profit: number;
  tally_error?: string;
}

export function getTrialBalance(clientId: string, fromDate?: string, toDate?: string) {
  const p = new URLSearchParams({ client_id: clientId, report_type: "trial_balance" });
  if (fromDate) p.set("from_date", fromDate);
  if (toDate) p.set("to_date", toDate);
  return api.get<TrialBalanceReport>(`/api/v1/reports/tally?${p}`);
}

export function getPLReport(clientId: string, fromDate?: string, toDate?: string) {
  const p = new URLSearchParams({ client_id: clientId, report_type: "profit_loss" });
  if (fromDate) p.set("from_date", fromDate);
  if (toDate) p.set("to_date", toDate);
  return api.get<PLReport>(`/api/v1/reports/tally?${p}`);
}

// ── Bank Reconciliation ────────────────────────────────────────────────────────
export interface BankTransaction {
  id: string;
  date: string;
  description: string;
  debit: number;
  credit: number;
  balance: number;
  matched: boolean;
  tally_ref: string | null;
  suggested?: string | null;
}

export interface ReconciliationSummary {
  total: number;
  matched: number;
  unmatched: number;
  total_credits: number;
  total_debits: number;
  closing_balance: number;
}

export interface Reconciliation {
  id: string;
  client_id: string;
  client_name: string;
  filename: string;
  uploaded_at: string;
  status: string;
  transactions: BankTransaction[];
  summary: ReconciliationSummary;
}

export async function uploadBankStatement(clientId: string, file: File): Promise<Reconciliation> {
  const formData = new FormData();
  formData.append("file", file);
  const headers = authHeaders();
  const res = await fetch(`${BASE}/api/v1/bank-reconciliation/upload?client_id=${clientId}`, {
    method: "POST", headers, body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Upload failed" }));
    throw new Error(err.detail ?? "Upload failed");
  }
  return res.json();
}

export function getReconciliation(id: string) {
  return api.get<Reconciliation>(`/api/v1/bank-reconciliation/${id}`);
}

export function getReconciliationsByClient(clientId: string) {
  return api.get<Reconciliation[]>(`/api/v1/bank-reconciliation/client/${clientId}`);
}

export function updateReconciliation(
  id: string,
  payload: Partial<{ status: string; bank_account: string; statement_balance: number }>
) {
  return api.patch<Reconciliation>(`/api/v1/bank-reconciliation/${id}`, payload);
}

export function deleteReconciliation(id: string) {
  return api.delete<{ ok: boolean }>(`/api/v1/bank-reconciliation/${id}`);
}

export function matchTransaction(recId: string, transactionId: string, tallyRef: string) {
  return api.post<Reconciliation>(`/api/v1/bank-reconciliation/${recId}/match`, {
    transaction_id: transactionId,
    tally_ref: tallyRef,
  });
}

export function unmatchTransaction(recId: string, transactionId: string) {
  return api.post<Reconciliation>(`/api/v1/bank-reconciliation/${recId}/unmatch`, {
    transaction_id: transactionId,
  });
}

// ── Month-end Checklist ────────────────────────────────────────────────────────
export interface ChecklistItem {
  id: string;
  category: string;
  task: string;
  description: string;
  priority: "high" | "medium" | "low";
  status: "pending" | "complete" | "na";
  completed_by: string | null;
  completed_at: string | null;
  notes: string;
}

export interface ChecklistSummary {
  total: number;
  complete: number;
  pending: number;
  na: number;
}

export interface Checklist {
  client_id: string;
  period: string;
  items: ChecklistItem[];
  summary: ChecklistSummary;
}

export function getChecklist(clientId: string, period?: string) {
  const p = new URLSearchParams();
  if (period) p.set("period", period);
  return api.get<Checklist>(`/api/v1/checklist/${clientId}?${p}`);
}

export function updateChecklistItem(
  clientId: string,
  itemId: string,
  status: "pending" | "complete" | "na",
  period?: string,
  notes?: string
) {
  const p = new URLSearchParams();
  if (period) p.set("period", period);
  return api.put<Checklist>(`/api/v1/checklist/${clientId}/${itemId}?${p}`, { status, notes });
}

export function resetChecklist(clientId: string, period?: string) {
  const p = new URLSearchParams();
  if (period) p.set("period", period);
  return api.post<Checklist>(`/api/v1/checklist/${clientId}/reset?${p}`, {});
}

// ── Tenants (super_admin) ──────────────────────────────────────────────────────
export interface TenantSummary {
  id: string;
  name: string;
  slug: string;
  contact_email?: string;
  plan: string;
  is_active: boolean;
  user_count: number;
  client_count: number;
  created_at: string;
}

export interface CreateTenantPayload {
  name: string;
  contact_email?: string;
  contact_phone?: string;
  plan?: string;
  notes?: string;
  admin_email: string;
  admin_password: string;
  admin_full_name?: string;
}

export function getTenants() {
  return api.get<TenantSummary[]>("/api/v1/tenants");
}

export function createTenant(payload: CreateTenantPayload) {
  return api.post<{ id: string; name: string; admin_email: string; message: string }>("/api/v1/tenants", payload);
}

export function updateTenant(
  id: string,
  payload: Partial<{ name: string; plan: string; is_active: boolean; notes: string }>
) {
  return api.patch<TenantSummary>(`/api/v1/tenants/${id}`, payload);
}

export function deleteTenant(id: string) {
  return api.delete<void>(`/api/v1/tenants/${id}`);
}

// ── Dashboard ─────────────────────────────────────────────────────────────────
export interface DashboardStats {
  activeClients: number;
  documents: number;
  vouchers: number;
  complianceAlerts: number;
}

export interface ActivityItem {
  client: string;
  action: string;
  time: string;
  status: "success" | "warning" | "danger" | "default";
}

export interface DashboardExtraStats {
  pendingVouchers?: number;
  submittedVouchers?: number;
  approvedVouchers?: number;
  postedVouchers?: number;
  rejectedVouchers?: number;
  tallyConnected?: number;
  reviewDocs?: number;
}

export interface DashboardData {
  stats: DashboardStats;
  recentActivity: ActivityItem[];
  extraStats?: DashboardExtraStats;
}

export function getDashboard(): Promise<DashboardData> {
  return api.get<DashboardData>("/api/v1/dashboard");
}

// ── Ledgers ───────────────────────────────────────────────────────────────────
export interface Ledger {
  id: string;
  name: string;
  tally_name: string;
  group?: string;
  description?: string;
  is_active: boolean;
}

export function getLedgers(): Promise<Ledger[]> {
  return api.get<Ledger[]>("/api/v1/ledgers/");
}

export function createLedger(payload: {
  name: string;
  tally_name: string;
  group?: string;
  description?: string;
}) {
  return api.post<Ledger>("/api/v1/ledgers/", payload);
}

export function updateLedger(id: string, payload: Partial<Ledger>) {
  return api.patch<Ledger>(`/api/v1/ledgers/${id}`, payload);
}

// ── Connector Key (Tally Windows agent auth) ──────────────────────────────────
export interface ConnectorKeyResponse {
  connector_api_key: string | null;
  tenant_id: string;
}

export function getConnectorKey() {
  return api.get<ConnectorKeyResponse>("/api/v1/connector/key");
}

export function regenerateConnectorKey() {
  return api.post<ConnectorKeyResponse>("/api/v1/connector/key/regenerate", {});
}