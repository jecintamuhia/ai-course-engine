import { useEffect, useState } from "react";
import { Activity, RefreshCw } from "lucide-react";

import { PageHeader } from "@/components/shared/PageHeader";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { LoadingState } from "@/components/shared/LoadingState";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

import { api } from "@/lib/api";
import type { MoodleConnectionCheck } from "@/lib/types";

export function SystemStatusPage() {
  const [loading, setLoading] = useState(true);
  const [check, setCheck] = useState<MoodleConnectionCheck | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      setCheck(await api.moodleCheck());
    } catch {
      setCheck(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  return (
    <>
      <PageHeader
        eyebrow="Platform"
        title="System status"
        description="Moodle connection — detailed read-only check."
        actions={
          <Button variant="outline" size="sm" onClick={load} disabled={loading}>
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
            Re-check
          </Button>
        }
      />

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-sm">
            <Activity className="h-4 w-4 text-oxford" />
            Moodle connection — detailed check
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <LoadingState message="Querying Moodle…" />
          ) : !check ? (
            <div className="py-10 text-center text-sm text-muted-foreground">
              Moodle check unavailable.
            </div>
          ) : (
            <div className="space-y-5">
              <div className="flex flex-wrap items-center gap-2">
                <StatusBadge
                  tone={check.configured ? "success" : "neutral"}
                  label={check.configured ? "Configured" : "Not configured"}
                />
                <StatusBadge
                  tone={check.connected ? "success" : "danger"}
                  label={check.connected ? "Connected" : "Disconnected"}
                />
                {check.default_category_found === false && (
                  <StatusBadge
                    tone="danger"
                    label={`Category ${check.default_category_id} not found`}
                  />
                )}
              </div>

              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                <Kv label="Site" value={check.site_name ?? "—"} />
                <Kv label="Site URL" value={check.site_url ?? "—"} mono />
                <Kv label="API version" value={check.api_version ?? "—"} />
                <Kv label="Web service user" value={check.username ?? "—"} />
                <Kv label="Default category id" value={check.default_category_id ?? "—"} />
                <Kv label="Visible categories" value={check.categories_visible} />
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {check?.error && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="p-5 text-sm text-red-800">
            <strong>Connection error:</strong> {check.error}
          </CardContent>
        </Card>
      )}

      {check?.configured && check.connected && check.default_category_found === false && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="p-5 text-sm text-red-800">
            The configured default category (id {check.default_category_id}) was not found or
            is not visible to this token. Publishing will fail until it is fixed.
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>What the check does</CardTitle>
          <CardDescription>
            Runs read-only Moodle web service calls:{" "}
            <code className="rounded bg-muted px-1 py-0.5 font-mono text-[11px]">
              core_webservice_get_site_info
            </code>{" "}
            to confirm the token works, and{" "}
            <code className="rounded bg-muted px-1 py-0.5 font-mono text-[11px]">
              core_course_get_categories
            </code>{" "}
            to confirm the configured category exists and how many categories the token can see.
            Nothing is written to Moodle.
          </CardDescription>
        </CardHeader>
      </Card>
    </>
  );
}

function Kv({
  label,
  value,
  mono,
}: {
  label: string;
  value: string | number | null;
  mono?: boolean;
}) {
  return (
    <div className="rounded-xl border border-border bg-cream-50/70 px-3.5 py-3">
      <div className="flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        <span aria-hidden className="h-1 w-1 rounded-full bg-oxford/60" />
        {label}
      </div>
      <div
        className={`tnum mt-1 font-semibold text-ink ${mono ? "font-mono text-xs" : "text-sm"}`}
      >
        {value ?? "—"}
      </div>
    </div>
  );
}