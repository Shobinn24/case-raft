import { useEffect, useState, useMemo } from "react";
import { Link } from "react-router-dom";
import { getCases, generateBatchReports, getReportDownloadUrl } from "../services/api";

const STATUS_TABS = ["all", "open", "pending", "closed"];

export default function Cases() {
  const [cases, setCases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [selected, setSelected] = useState(new Set());
  const [batchGenerating, setBatchGenerating] = useState(false);
  const [batchResult, setBatchResult] = useState(null);

  useEffect(() => {
    getCases("open,pending,closed")
      .then((res) => setCases(res.data.data || []))
      .catch((err) => setError(err.response?.data?.error || "Failed to load cases"))
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    let result = cases;
    if (statusFilter !== "all") {
      result = result.filter((c) => c.status?.toLowerCase() === statusFilter);
    }
    if (search.trim()) {
      const q = search.toLowerCase();
      result = result.filter(
        (c) =>
          c.display_number?.toLowerCase().includes(q) ||
          c.description?.toLowerCase().includes(q) ||
          c.client?.name?.toLowerCase().includes(q)
      );
    }
    return result;
  }, [cases, statusFilter, search]);

  const toggleSelect = (id) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (selected.size === filtered.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(filtered.map((c) => c.id)));
    }
  };

  const handleBatchGenerate = async () => {
    setBatchGenerating(true);
    setBatchResult(null);
    try {
      const res = await generateBatchReports([...selected]);
      setBatchResult(res.data);
      setSelected(new Set());
    } catch (err) {
      setError(err.response?.data?.error || "Batch generation failed");
    } finally {
      setBatchGenerating(false);
    }
  };

  if (loading) return <div className="loading">Loading cases...</div>;
  if (error && cases.length === 0) return <div className="error">{error}</div>;

  return (
    <div>
      <h2>Your Cases</h2>

      {/* Toolbar: Search + Filter */}
      <div className="cases-toolbar">
        <input
          type="text"
          className="cases-search"
          placeholder="Search by case number, description, or client..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <div className="filter-tabs">
          {STATUS_TABS.map((tab) => (
            <button
              key={tab}
              className={`filter-tab ${statusFilter === tab ? "active" : ""}`}
              onClick={() => setStatusFilter(tab)}
            >
              {tab === "all" ? "All" : tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* Batch Actions */}
      {selected.size > 0 && (
        <div className="batch-bar">
          <span>{selected.size} case{selected.size !== 1 ? "s" : ""} selected</span>
          <div className="batch-bar-actions">
            <button className="btn btn-small btn-outline" onClick={toggleAll}>
              {selected.size === filtered.length ? "Deselect All" : "Select All"}
            </button>
            <button
              className="btn btn-small btn-accent"
              onClick={handleBatchGenerate}
              disabled={batchGenerating}
            >
              {batchGenerating ? "Generating..." : "Generate Batch Reports"}
            </button>
          </div>
        </div>
      )}

      {/* Batch Result */}
      {batchResult && (
        <div className="report-success" style={{ marginBottom: 16 }}>
          <p>{batchResult.reports.length} report{batchResult.reports.length !== 1 ? "s" : ""} generated!</p>
          <Link to="/history" className="btn btn-small btn-secondary">
            View in History
          </Link>
        </div>
      )}

      {error && <p className="error" style={{ marginBottom: 16 }}>{error}</p>}

      {filtered.length === 0 ? (
        <p className="empty">
          {cases.length === 0 ? "No cases found in Clio." : "No cases match your filters."}
        </p>
      ) : (
        <div className="case-grid">
          {filtered.map((c) => (
            <div key={c.id} className={`case-card ${selected.has(c.id) ? "selected" : ""}`}>
              <input
                type="checkbox"
                className="case-checkbox"
                checked={selected.has(c.id)}
                onChange={() => toggleSelect(c.id)}
                title="Select for batch report"
              />
              <Link to={`/cases/${c.id}`}>
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
                  {c.practice_area?.name && <span>Area: {c.practice_area.name}</span>}
                </div>
              </Link>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
