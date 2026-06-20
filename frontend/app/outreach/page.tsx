"use client";

import { useEffect, useState, useCallback } from "react";
import {
  CheckCircle2,
  XCircle,
  Send,
  AlertCircle,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  Loader2,
  Pencil,
} from "lucide-react";
import PageHeader from "@/components/PageHeader";
import StatusBadge from "@/components/StatusBadge";
import { api } from "@/lib/api";
import type { OutreachDraft } from "@/lib/types";

type Filter = "pending_review" | "approved" | "sent" | "all";

const FILTER_TABS: { value: Filter; label: string }[] = [
  { value: "pending_review", label: "Pending Review" },
  { value: "approved", label: "Approved" },
  { value: "sent", label: "Sent" },
  { value: "all", label: "All" },
];

interface EditForm {
  email: string;
  subject: string;
  body: string;
}

interface DraftRowProps {
  draft: OutreachDraft;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
  onSend: (id: string) => void;
  onSave: (id: string, form: EditForm) => Promise<void>;
  busy: boolean;
}

function DraftRow({ draft, onApprove, onReject, onSend, onSave, busy }: DraftRowProps) {
  const [expanded, setExpanded] = useState(false);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<EditForm>({
    email: draft.email ?? "",
    subject: draft.subject,
    body: draft.body,
  });

  const canEdit = draft.status === "pending_review" || draft.status === "approved";

  useEffect(() => {
    if (!editing) {
      setForm({
        email: draft.email ?? "",
        subject: draft.subject,
        body: draft.body,
      });
    }
  }, [draft, editing]);

  async function handleSave(e: React.MouseEvent) {
    e.stopPropagation();
    await onSave(draft.id, form);
    setEditing(false);
  }

  function handleCancel(e: React.MouseEvent) {
    e.stopPropagation();
    setForm({
      email: draft.email ?? "",
      subject: draft.subject,
      body: draft.body,
    });
    setEditing(false);
  }

  return (
    <div className="border border-zinc-800/60 rounded-xl overflow-hidden bg-zinc-900/40">
      <div
        className="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-zinc-800/20 transition-colors"
        onClick={() => setExpanded((e) => !e)}
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-medium text-zinc-200 text-sm">{draft.contact_name}</span>
            <span className="text-zinc-600 text-xs">·</span>
            <span className="text-zinc-400 text-xs">{draft.company_name}</span>
            {draft.email && (
              <>
                <span className="text-zinc-600 text-xs">·</span>
                <span className="text-zinc-500 text-xs">{draft.email}</span>
              </>
            )}
            {!draft.email && (
              <>
                <span className="text-zinc-600 text-xs">·</span>
                <span className="text-amber-500/80 text-xs">no email — edit to add</span>
              </>
            )}
          </div>
          <p className="text-xs text-zinc-500 mt-0.5 truncate">{draft.subject}</p>
        </div>
        <StatusBadge status={draft.status} />
        {expanded ? (
          <ChevronUp className="w-4 h-4 text-zinc-600 shrink-0" />
        ) : (
          <ChevronDown className="w-4 h-4 text-zinc-600 shrink-0" />
        )}
      </div>

      {expanded && (
        <div className="border-t border-zinc-800/60 px-4 pb-4 pt-3">
          {!editing && draft.hook && (
            <p className="text-xs text-violet-400 mb-2">
              <span className="text-zinc-500">Hook: </span>{draft.hook}
            </p>
          )}
          {!editing && draft.signal_used && (
            <p className="text-xs text-zinc-500 mb-3">
              <span className="text-zinc-600">Signal: </span>{draft.signal_used}
            </p>
          )}

          {editing ? (
            <div className="space-y-3 mb-4" onClick={(e) => e.stopPropagation()}>
              <label className="block">
                <span className="text-xs text-zinc-500 block mb-1">To (email)</span>
                <input
                  type="email"
                  value={form.email}
                  onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                  placeholder="prospect@company.com"
                  className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-violet-500"
                />
              </label>
              <label className="block">
                <span className="text-xs text-zinc-500 block mb-1">Subject</span>
                <input
                  type="text"
                  value={form.subject}
                  onChange={(e) => setForm((f) => ({ ...f, subject: e.target.value }))}
                  className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-violet-500"
                />
              </label>
              <label className="block">
                <span className="text-xs text-zinc-500 block mb-1">Body</span>
                <textarea
                  value={form.body}
                  onChange={(e) => setForm((f) => ({ ...f, body: e.target.value }))}
                  rows={10}
                  className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 font-mono leading-relaxed focus:outline-none focus:border-violet-500 resize-y min-h-[160px]"
                />
              </label>
              {draft.status === "approved" && (
                <p className="text-[11px] text-amber-400/90">
                  Saving will move this draft back to pending review for re-approval.
                </p>
              )}
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  disabled={busy}
                  onClick={handleSave}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-violet-600 hover:bg-violet-500 text-white text-xs font-medium disabled:opacity-50"
                >
                  {busy ? <Loader2 className="w-3 h-3 animate-spin" /> : null}
                  Save changes
                </button>
                <button
                  type="button"
                  disabled={busy}
                  onClick={handleCancel}
                  className="px-3 py-1.5 rounded-lg border border-zinc-700 text-zinc-400 hover:text-zinc-200 text-xs"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-4 mb-4 font-mono text-xs leading-relaxed">
              <p className="text-zinc-400 mb-2">
                <span className="text-zinc-600">To: </span>{draft.email ?? "—"}
              </p>
              <p className="text-zinc-400 mb-3">
                <span className="text-zinc-600">Subject: </span>{draft.subject}
              </p>
              <hr className="border-zinc-800 mb-3" />
              <pre className="whitespace-pre-wrap text-zinc-300">{draft.body}</pre>
            </div>
          )}

          {!editing && (
            <div className="flex items-center gap-2 flex-wrap">
              {canEdit && (
                <button
                  disabled={busy}
                  onClick={(e) => {
                    e.stopPropagation();
                    setExpanded(true);
                    setEditing(true);
                  }}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs font-medium transition-colors disabled:opacity-50"
                >
                  <Pencil className="w-3 h-3" /> Edit
                </button>
              )}

              {draft.status === "pending_review" && (
                <>
                  <button
                    disabled={busy}
                    onClick={(e) => {
                      e.stopPropagation();
                      onApprove(draft.id);
                    }}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-400 text-xs font-medium transition-colors disabled:opacity-50"
                  >
                    {busy ? (
                      <Loader2 className="w-3 h-3 animate-spin" />
                    ) : (
                      <CheckCircle2 className="w-3 h-3" />
                    )}
                    Approve
                  </button>
                  <button
                    disabled={busy}
                    onClick={(e) => {
                      e.stopPropagation();
                      onReject(draft.id);
                    }}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-rose-600/20 hover:bg-rose-600/30 text-rose-400 text-xs font-medium transition-colors disabled:opacity-50"
                  >
                    <XCircle className="w-3 h-3" /> Reject
                  </button>
                </>
              )}

              {draft.status === "approved" && (
                <>
                  {!draft.email?.trim() && (
                    <p className="text-xs text-amber-400 mb-2">
                      Add a recipient email via Edit before sending.
                    </p>
                  )}
                  <button
                    disabled={busy || !draft.email?.trim()}
                    onClick={(e) => {
                      e.stopPropagation();
                      onSend(draft.id);
                    }}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-violet-600/20 hover:bg-violet-600/30 text-violet-400 text-xs font-medium transition-colors disabled:opacity-50"
                  >
                    {busy ? <Loader2 className="w-3 h-3 animate-spin" /> : <Send className="w-3 h-3" />}
                    Send Email
                  </button>
                </>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function OutreachPage() {
  const [filter, setFilter] = useState<Filter>("pending_review");
  const [drafts, setDrafts] = useState<OutreachDraft[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const items = await api.outreach.listPending(50);
      const filtered =
        filter === "all" || filter === "pending_review"
          ? items
          : items.filter((d) => d.status === filter);
      setDrafts(filtered);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load drafts");
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleApprove(id: string) {
    setBusyId(id);
    try {
      const updated = await api.outreach.approve(id);
      setDrafts((ds) => ds.map((d) => (d.id === id ? updated : d)));
      showToast("Draft approved");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Approve failed");
    } finally {
      setBusyId(null);
    }
  }

  async function handleReject(id: string) {
    setBusyId(id);
    try {
      const updated = await api.outreach.reject(id);
      setDrafts((ds) => ds.map((d) => (d.id === id ? updated : d)));
      showToast("Draft rejected");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Reject failed");
    } finally {
      setBusyId(null);
    }
  }

  async function handleSend(id: string) {
    setBusyId(id);
    try {
      await api.outreach.send(id);
      setDrafts((ds) => ds.filter((d) => d.id !== id));
      showToast("Email sent!");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Send failed");
    } finally {
      setBusyId(null);
    }
  }

  async function handleSave(id: string, form: EditForm) {
    setBusyId(id);
    setError(null);
    try {
      const updated = await api.outreach.update(id, {
        email: form.email.trim() || null,
        subject: form.subject.trim(),
        body: form.body.trim(),
      });
      setDrafts((ds) => ds.map((d) => (d.id === id ? updated : d)));
      showToast(
        updated.status === "pending_review" && drafts.find((d) => d.id === id)?.status === "approved"
          ? "Saved — re-approval required"
          : "Draft updated"
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
      throw e;
    } finally {
      setBusyId(null);
    }
  }

  const pendingCount = drafts.filter((d) => d.status === "pending_review").length;

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <PageHeader
        title="Outreach Queue"
        subtitle="Review, edit, and send AI-drafted emails"
        action={
          <button
            onClick={load}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-zinc-800 hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 text-sm transition-colors"
          >
            <RefreshCw className="w-4 h-4" /> Refresh
          </button>
        }
      />

      <div className="flex gap-1 mb-5 bg-zinc-900/60 border border-zinc-800/60 rounded-lg p-1 w-fit">
        {FILTER_TABS.map(({ value, label }) => (
          <button
            key={value}
            onClick={() => setFilter(value)}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
              filter === value
                ? "bg-zinc-700 text-zinc-100"
                : "text-zinc-500 hover:text-zinc-300"
            }`}
          >
            {label}
            {value === "pending_review" && pendingCount > 0 && (
              <span className="ml-1.5 bg-amber-500/20 text-amber-400 rounded-full px-1.5 py-0.5 text-[10px]">
                {pendingCount}
              </span>
            )}
          </button>
        ))}
      </div>

      {error && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-rose-800/50 bg-rose-500/10 px-4 py-3 text-sm text-rose-400">
          <AlertCircle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-16 rounded-xl bg-zinc-900/60 border border-zinc-800/60 animate-pulse" />
          ))}
        </div>
      ) : drafts.length === 0 ? (
        <div className="text-center py-20 text-zinc-600">
          <p className="text-sm">No drafts in this queue.</p>
          {filter === "pending_review" && (
            <p className="text-xs mt-1">Run a campaign with personalization to generate drafts.</p>
          )}
        </div>
      ) : (
        <>
          <p className="text-xs text-zinc-600 mb-3">
            {drafts.length} draft{drafts.length !== 1 ? "s" : ""}
          </p>
          <div className="space-y-3">
            {drafts.map((d) => (
              <DraftRow
                key={d.id}
                draft={d}
                onApprove={handleApprove}
                onReject={handleReject}
                onSend={handleSend}
                onSave={handleSave}
                busy={busyId === d.id}
              />
            ))}
          </div>
        </>
      )}

      {toast && (
        <div className="fixed bottom-6 right-6 bg-zinc-800 border border-zinc-700 rounded-lg px-4 py-3 text-sm text-zinc-200 shadow-xl flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          {toast}
        </div>
      )}
    </div>
  );
}
