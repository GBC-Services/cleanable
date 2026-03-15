/**
 * ContractTab — Agency Contract Management
 * ==========================================
 *
 * Features:
 *   - Generate new contracts with geofence + pricing snapshots
 *   - View contract details (gated until fully signed)
 *   - Digital signature flow
 *   - Download signed PDF
 */

"use client";

import { useCallback, useEffect, useState } from "react";
import {
  FileText,
  Download,
  PenTool,
  Loader2,
  Shield,
  Clock,
  CheckCircle2,
  AlertTriangle,
  Lock,
  Plus,
  ChevronRight,
  Eye,
} from "lucide-react";
import { api } from "@/lib/api";
import { useAuthStore } from "@/lib/auth-store";
import type {
  AgencyContractListItem,
  AgencyContractDetail,
  ContractStatus,
  CONTRACT_STATUS_INFO,
} from "@/types/onboarding";

// ── Status badge config ──────────────────────────────────────────────

const STATUS_CONFIG: Record<ContractStatus, { label: string; icon: typeof Clock; color: string; bg: string }> = {
  draft: { label: "Draft", icon: FileText, color: "text-gray-600", bg: "bg-gray-100" },
  pending_signatures: { label: "Pending Signatures", icon: PenTool, color: "text-amber-700", bg: "bg-amber-50" },
  fully_signed: { label: "Fully Signed", icon: CheckCircle2, color: "text-green-700", bg: "bg-green-50" },
  expired: { label: "Expired", icon: Clock, color: "text-red-600", bg: "bg-red-50" },
  revoked: { label: "Revoked", icon: AlertTriangle, color: "text-red-700", bg: "bg-red-100" },
};

interface ContractTabProps {
  agencyId: number;
}

export default function ContractTab({ agencyId }: ContractTabProps) {
  const { user } = useAuthStore();
  const [contracts, setContracts] = useState<AgencyContractListItem[]>([]);
  const [selectedContract, setSelectedContract] = useState<AgencyContractDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [signing, setSigning] = useState(false);
  const [signerName, setSignerName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // ── Load contracts ─────────────────────────────────────────────────

  const loadContracts = useCallback(async () => {
    try {
      const data = await api.get<AgencyContractListItem[]>("/onboarding/contracts/");
      setContracts(data);
    } catch (err: any) {
      setError(err?.message || "Failed to load contracts");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadContracts();
  }, [loadContracts]);

  // ── Load contract detail ───────────────────────────────────────────

  const viewContract = async (uuid: string) => {
    try {
      const data = await api.get<AgencyContractDetail>(`/onboarding/contracts/${uuid}/`);
      setSelectedContract(data);
    } catch (err: any) {
      setError(err?.message || "Failed to load contract");
    }
  };

  // ── Generate new contract ──────────────────────────────────────────

  const generateContract = async () => {
    setGenerating(true);
    setError(null);
    try {
      const data = await api.post<AgencyContractDetail>("/onboarding/contracts/generate/", {
        agency_id: agencyId,
        expiry_months: 12,
      });
      setSelectedContract(data);
      await loadContracts();
      setSuccess("Contract generated. Review and sign below.");
    } catch (err: any) {
      setError(err?.message || "Failed to generate contract");
    } finally {
      setGenerating(false);
    }
  };

  // ── Sign contract ──────────────────────────────────────────────────

  const signContract = async () => {
    if (!selectedContract || !signerName.trim()) return;
    setSigning(true);
    setError(null);

    const signerRole =
      user?.role === 20 ? "platform_admin" : "agency_owner";

    try {
      const result = await api.post(
        `/onboarding/contracts/${selectedContract.uuid}/sign/`,
        {
          signer_full_name: signerName,
          signer_role: signerRole,
        }
      );
      setSuccess(
        (result as any).is_fully_signed
          ? "Contract is now fully signed. PDF is accessible."
          : "Signature recorded. Awaiting remaining signatures."
      );
      // Reload contract detail
      await viewContract(selectedContract.uuid);
      await loadContracts();
    } catch (err: any) {
      setError(err?.message || "Failed to sign contract");
    } finally {
      setSigning(false);
    }
  };

  // ── Check if current user has already signed ───────────────────────

  const hasCurrentUserSigned = () => {
    if (!selectedContract || !user) return false;
    const signerRole = user.role === 20 ? "platform_admin" : "agency_owner";
    return selectedContract.signatures.some(
      (s) => s.signer_role === signerRole && s.is_valid
    );
  };

  // ── Render: Contract Detail ────────────────────────────────────────

  if (selectedContract) {
    const statusCfg = STATUS_CONFIG[selectedContract.status];
    const StatusIcon = statusCfg.icon;
    const userSigned = hasCurrentUserSigned();
    const canSign =
      selectedContract.status === "pending_signatures" && !userSigned;

    return (
      <div className="space-y-6">
        {/* Back button */}
        <button
          onClick={() => setSelectedContract(null)}
          className="text-sm text-brand-600 hover:text-brand-700"
        >
          ← Back to contracts
        </button>

        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">
              {selectedContract.agency_name} — v{selectedContract.version}
            </h3>
            <div className="mt-1 flex items-center gap-2">
              <span
                className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5
                            text-xs font-medium ${statusCfg.color} ${statusCfg.bg}`}
              >
                <StatusIcon className="h-3 w-3" />
                {statusCfg.label}
              </span>
              <span className="text-xs text-gray-400">
                Created {new Date(selectedContract.created_at).toLocaleDateString()}
              </span>
            </div>
          </div>

          {selectedContract.pdf_file && selectedContract.status === "fully_signed" && (
            <a
              href={selectedContract.pdf_file}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 rounded-lg bg-brand-500 px-4 py-2
                         text-sm font-medium text-white hover:bg-brand-600"
            >
              <Download className="h-4 w-4" />
              Download PDF
            </a>
          )}
        </div>

        {error && (
          <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</div>
        )}
        {success && (
          <div className="rounded-lg bg-green-50 p-3 text-sm text-green-700">{success}</div>
        )}

        {/* Access Gate */}
        {selectedContract.status !== "fully_signed" && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
            <div className="flex items-center gap-2">
              <Lock className="h-5 w-5 text-amber-600" />
              <p className="text-sm font-medium text-amber-800">
                Contract access restricted until all parties have signed.
              </p>
            </div>
            <p className="mt-1 text-xs text-amber-600">
              {selectedContract.signatures.length} of{" "}
              {selectedContract.required_signers.length} signatures collected
            </p>
          </div>
        )}

        {/* Service Areas Snapshot */}
        {selectedContract.status === "fully_signed" && (
          <div className="rounded-lg border border-gray-200 bg-white p-4">
            <h4 className="mb-3 text-sm font-semibold text-gray-900">
              Service Areas (at signing)
            </h4>
            <div className="space-y-2">
              {selectedContract.service_areas_snapshot.map((area, i) => (
                <div
                  key={i}
                  className="flex items-center gap-2 rounded-md bg-gray-50 px-3 py-2"
                >
                  <div
                    className="h-2.5 w-2.5 rounded-full"
                    style={{ backgroundColor: area.color }}
                  />
                  <span className="text-sm text-gray-700">{area.name}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Pricing Snapshot */}
        {selectedContract.status === "fully_signed" &&
          selectedContract.pricing_snapshot?.fees?.length > 0 && (
            <div className="rounded-lg border border-gray-200 bg-white p-4">
              <h4 className="mb-3 text-sm font-semibold text-gray-900">
                Pricing Schedule (at signing)
              </h4>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200">
                    <th className="pb-2 text-left text-xs font-medium text-gray-500">Service</th>
                    <th className="pb-2 text-right text-xs font-medium text-gray-500">Client Fee</th>
                    <th className="pb-2 text-right text-xs font-medium text-gray-500">Subcontractor</th>
                  </tr>
                </thead>
                <tbody>
                  {selectedContract.pricing_snapshot.fees.map((fee, i) => (
                    <tr key={i} className="border-b border-gray-100">
                      <td className="py-2 text-gray-700">{fee.service_name}</td>
                      <td className="py-2 text-right text-gray-900">${fee.client_fee}</td>
                      <td className="py-2 text-right text-gray-500">${fee.subcontractor_fee}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

        {/* Signatures */}
        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <h4 className="mb-3 text-sm font-semibold text-gray-900">
            Digital Signatures
          </h4>
          <div className="space-y-3">
            {selectedContract.required_signers.map((req, i) => {
              const sig = selectedContract.signatures.find(
                (s) => s.signer_role === req.role && s.is_valid
              );
              const roleLabel = req.role.replace("_", " ").replace(/\b\w/g, (l: string) => l.toUpperCase());
              return (
                <div key={i} className="flex items-center justify-between rounded-md border border-gray-100 p-3">
                  <div className="flex items-center gap-3">
                    {sig ? (
                      <CheckCircle2 className="h-5 w-5 text-green-500" />
                    ) : (
                      <Clock className="h-5 w-5 text-gray-300" />
                    )}
                    <div>
                      <p className="text-sm font-medium text-gray-900">{roleLabel}</p>
                      {sig && (
                        <p className="text-xs text-gray-500">
                          Signed by {sig.signer_full_name} on{" "}
                          {new Date(sig.signed_at).toLocaleString()}
                        </p>
                      )}
                    </div>
                  </div>
                  {sig && (
                    <span className="rounded-full bg-green-50 px-2 py-0.5 text-xs font-medium text-green-700">
                      Verified
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Sign Form */}
        {canSign && (
          <div className="rounded-lg border border-brand-200 bg-brand-50 p-4">
            <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold text-brand-900">
              <PenTool className="h-4 w-4" />
              Sign This Contract
            </h4>
            <p className="mb-3 text-xs text-brand-700">
              By signing, you acknowledge this is a legally binding agreement under
              the ESIGN Act. Your IP address and timestamp will be recorded.
            </p>
            <div className="flex gap-2">
              <input
                type="text"
                value={signerName}
                onChange={(e) => setSignerName(e.target.value)}
                placeholder="Type your full legal name"
                className="flex-1 rounded-lg border border-brand-300 bg-white px-3 py-2
                           text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
              />
              <button
                onClick={signContract}
                disabled={signing || !signerName.trim()}
                className="flex items-center gap-2 rounded-lg bg-brand-500 px-4 py-2
                           text-sm font-medium text-white hover:bg-brand-600
                           disabled:opacity-50"
              >
                {signing ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Shield className="h-4 w-4" />
                )}
                Sign
              </button>
            </div>
          </div>
        )}

        {/* Document Hash */}
        {selectedContract.document_hash && (
          <div className="rounded-lg bg-gray-50 p-3">
            <p className="text-xs text-gray-500">
              <span className="font-medium">Document Hash (SHA-256):</span>{" "}
              <code className="text-xs">{selectedContract.document_hash}</code>
            </p>
          </div>
        )}
      </div>
    );
  }

  // ── Render: Contract List ──────────────────────────────────────────

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
          <FileText className="h-5 w-5 text-brand-500" />
          Contracts
        </h3>
        <button
          onClick={generateContract}
          disabled={generating}
          className="flex items-center gap-1.5 rounded-lg bg-brand-500 px-3 py-1.5
                     text-sm font-medium text-white hover:bg-brand-600 disabled:opacity-50"
        >
          {generating ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Plus className="h-4 w-4" />
          )}
          Generate Contract
        </button>
      </div>

      {error && (
        <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</div>
      )}
      {success && (
        <div className="rounded-lg bg-green-50 p-3 text-sm text-green-700">{success}</div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-brand-500" />
        </div>
      ) : contracts.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-300 p-8 text-center">
          <FileText className="mx-auto h-8 w-8 text-gray-300" />
          <p className="mt-2 text-sm text-gray-500">
            No contracts yet. Define service areas first, then generate a contract.
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {contracts.map((contract) => {
            const cfg = STATUS_CONFIG[contract.status];
            const StatusIcon = cfg.icon;
            return (
              <button
                key={contract.uuid}
                onClick={() => viewContract(contract.uuid)}
                className="w-full rounded-lg border border-gray-200 bg-white p-4 text-left
                           transition hover:border-gray-300 hover:shadow-sm"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-900">
                      {contract.agency_name} — v{contract.version}
                    </p>
                    <div className="mt-1 flex items-center gap-3">
                      <span
                        className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5
                                    text-xs font-medium ${cfg.color} ${cfg.bg}`}
                      >
                        <StatusIcon className="h-3 w-3" />
                        {cfg.label}
                      </span>
                      <span className="text-xs text-gray-400">
                        {contract.signatures_count}/{contract.required_signatures_count} signed
                      </span>
                      {contract.expiry_date && (
                        <span className="text-xs text-gray-400">
                          Expires {new Date(contract.expiry_date).toLocaleDateString()}
                        </span>
                      )}
                    </div>
                  </div>
                  <ChevronRight className="h-5 w-5 text-gray-400" />
                </div>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
