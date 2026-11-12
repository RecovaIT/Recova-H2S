"use client";

import React, { useState } from "react";
import { Download, FileCode2, Send } from "lucide-react";
import { opsService } from "@/services/ops";
import { downloadJsonFile } from "@/lib/utils";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { useToast } from "@/components/ui/toast";

export function FhirBundleModal({
  patientId,
  patientLabel,
  open,
  onOpenChange,
}: {
  patientId: string;
  patientLabel: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { pushToast } = useToast();
  const [loading, setLoading] = useState(false);
  const [pushing, setPushing] = useState(false);
  const [bundleType, setBundleType] = useState<"collection" | "transaction">("collection");
  const [data, setData] = useState<{
    bundle: Record<string, unknown>;
    validation: Record<string, unknown>;
  } | null>(null);
  const [malaffiResult, setMalaffiResult] = useState<Record<string, unknown> | null>(null);

  const loadBundle = async (type: "collection" | "transaction") => {
    setBundleType(type);
    setLoading(true);
    try {
      const res = await opsService.exportPatientFhir(patientId, type);
      setData(res);
    } catch (err) {
      pushToast("FHIR export failed", "error", err instanceof Error ? err.message : undefined);
    } finally {
      setLoading(false);
    }
  };

  const handleMalaffiPush = async () => {
    setPushing(true);
    try {
      const res = await opsService.pushToMalaffi(patientId);
      setMalaffiResult(res);
      pushToast("Malaffi adapter executed", "info", `Status: ${String(res.status || "checked")}`);
    } catch (err) {
      pushToast("Malaffi push failed", "error", err instanceof Error ? err.message : undefined);
    } finally {
      setPushing(false);
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={`FHIR R4 Bundle — ${patientLabel}`}
      description="UAE ADHICS / Malaffi HL7 FHIR R4 interoperability export & schema validator."
      maxWidthClass="max-w-4xl"
    >
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" onClick={() => void loadBundle("collection")} disabled={loading}>
            <FileCode2 className="h-4 w-4" /> Generate Collection Bundle
          </Button>
          <Button size="sm" variant="outline" onClick={() => void loadBundle("transaction")} disabled={loading}>
            Generate Transaction Bundle
          </Button>
          {data && (
            <>
              <Button
                size="sm"
                variant="outline"
                onClick={() => downloadJsonFile(`recova-fhir-${patientId.slice(0, 8)}-${bundleType}.json`, data.bundle)}
              >
                <Download className="h-4 w-4" /> Download JSON
              </Button>
              <Button size="sm" variant="secondary" onClick={() => void handleMalaffiPush()} disabled={pushing}>
                <Send className="h-4 w-4" /> {pushing ? "Pushing..." : "Push to Malaffi HIE"}
              </Button>
            </>
          )}
        </div>

        {malaffiResult && (
          <Alert
            variant={malaffiResult.status === "delivered" ? "success" : "warning"}
            title={`Malaffi HIE Adapter Status: ${String(malaffiResult.status || "unknown")}`}
          >
            {String(malaffiResult.detail || malaffiResult.message || JSON.stringify(malaffiResult))}
          </Alert>
        )}

        {data && (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <Badge variant={data.validation.valid ? "success" : "danger"}>
                {data.validation.valid ? "FHIR R4 Validated" : "Validation Errors"}
              </Badge>
              <Badge variant="outline">
                Entries: {String(data.validation.total_entries ?? 0)}
              </Badge>
              {Array.isArray(data.validation.resource_types) && (
                <Badge variant="secondary">
                  Resources: {(data.validation.resource_types as string[]).join(", ")}
                </Badge>
              )}
            </div>
            <pre className="max-h-96 overflow-auto rounded-lg bg-slate-900 p-3.5 text-xs text-slate-100">
              {JSON.stringify(data.bundle, null, 2)}
            </pre>
          </div>
        )}

        {!data && !loading && (
          <Alert variant="info">
            Note: Patient must have an active <code>hie_sharing</code> consent before FHIR bundles can be exported or transmitted.
          </Alert>
        )}
      </div>
    </Dialog>
  );
}
