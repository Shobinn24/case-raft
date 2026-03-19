import { useEffect, useState } from "react";
import { getReportHistory, getReportDownloadUrl } from "../services/api";
import SEO from "../components/SEO";

export default function History() {
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getReportHistory()
      .then((res) => setReports(res.data.reports || []))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="loading">Loading history...</div>;

  return (
    <section>
      <SEO title="Report History" description="View and re-download all previously generated case reports." path="/history" />
      <h2>Report History</h2>
      {reports.length === 0 ? (
        <p className="empty">No reports generated yet.</p>
      ) : (
        <table className="history-table">
          <thead>
            <tr>
              <th>Report Subject</th>
              <th>Report Type</th>
              <th>Generated</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {reports.map((r) => (
              <tr key={r.id}>
                <td>{r.case_name}</td>
                <td>{r.report_type.replaceAll("_", " ")}</td>
                <td>{new Date(r.generated_at).toLocaleDateString()}</td>
                <td>
                  <a
                    href={getReportDownloadUrl(r.id)}
                    className="btn btn-small"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Download
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
