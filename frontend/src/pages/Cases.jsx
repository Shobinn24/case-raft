import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getCases } from "../services/api";

export default function Cases() {
  const [cases, setCases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    getCases("open,pending,closed")
      .then((res) => setCases(res.data.data || []))
      .catch((err) => setError(err.response?.data?.error || "Failed to load cases"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="loading">Loading cases...</div>;
  if (error) return <div className="error">{error}</div>;

  return (
    <div>
      <h2>Your Cases</h2>
      {cases.length === 0 ? (
        <p className="empty">No cases found in Clio.</p>
      ) : (
        <div className="case-grid">
          {cases.map((c) => (
            <Link to={`/cases/${c.id}`} key={c.id} className="case-card">
              <div className="case-card-header">
                <span className="case-number">{c.display_number}</span>
                <span className={`status-badge status-${c.status?.toLowerCase()}`}>
                  {c.status}
                </span>
              </div>
              <p className="case-description">
                {c.description || "No description"}
              </p>
              <div className="case-meta">
                {c.client?.name && <span>Client: {c.client.name}</span>}
                {c.practice_area?.name && (
                  <span>Area: {c.practice_area.name}</span>
                )}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
