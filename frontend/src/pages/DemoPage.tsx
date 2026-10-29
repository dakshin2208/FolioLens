import { FlaskConical, Send, Upload } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ReportView } from "../components/ReportView";
import { Avatar, Badge, Notice, PageHeader, PageSkeleton, buttonCls, useDocumentTitle } from "../components/ui";
import { api, auth } from "../lib/api";
import type { Report } from "../lib/types";

export function DemoPage() {
  useDocumentTitle("Demo portfolio");
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api.demoReport().then(setReport).catch((e) => setError(e.message));
  }, []);
  const signedIn = Boolean(auth.token);
  return (
    <div className="space-y-6">
      <PageHeader
        leading={<Avatar name="Sample Client" size={52} />}
        title="Sample Client"
        subtitle={`Core portfolio · ${report?.overview.holdings_count ?? 10} holdings · ${report?.overview.funds_count ?? 7} funds, ${report?.overview.stocks_count ?? 3} stocks`}
        meta={<Badge tone="warn" icon={FlaskConical}>Sample data: every company, fund and price is made up</Badge>}
        actions={
          <>
            <Link to={signedIn ? "/app" : "/register"} className={buttonCls("secondary")}>
              <Upload size={16} /> Try with a real statement
            </Link>
            <Link to="/demo/share" className={buttonCls("primary")}>
              <Send size={16} /> Client report
            </Link>
          </>
        }
      />
      {error && <Notice level="error" title="Could not load the demo">{error}</Notice>}
      {!report && !error && <PageSkeleton />}
      {report && <ReportView report={report} storageKey="demo" shareHref="/demo/share" />}
    </div>
  );
}
