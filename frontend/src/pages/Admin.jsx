import { useEffect, useState } from "react";
import { getAdminStats, getAdminErrors, getAdminUsers } from "../services/api";
import SEO from "../components/SEO";

export default function Admin() {
  const [tab, setTab] = useState("errors");
  const [stats, setStats] = useState(null);
  const [errors, setErrors] = useState([]);
  const [errorsMeta, setErrorsMeta] = useState({ total: 0, page: 1, pages: 1 });
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedError, setExpandedError] = useState(null);

  // Filters
  const [statusFilter, setStatusFilter] = useState("");
  const [emailFilter, setEmailFilter] = useState("");
  const [endpointFilter, setEndpointFilter] = useState("");

  useEffect(() => {
    loadStats();
  }, []);

  useEffect(() => {
    if (tab === "errors") loadErrors(1);
    if (tab === "users") loadUsers();
  }, [tab]);

  const loadStats = async () => {
    try {
      const res = await getAdminStats();
      setStats(res.data);
    } catch {
      /* ignore */
    }
  };

  const loadErrors = async (page = 1) => {
    setLoading(true);
    try {
      const params = { page, per_page: 50 };
      if (statusFilter) params.status = statusFilter;
      if (emailFilter) params.email = emailFilter;
      if (endpointFilter) params.endpoint = endpointFilter;
      const res = await getAdminErrors(params);
      setErrors(res.data.errors);
      setErrorsMeta({
        total: res.data.total,
        page: res.data.page,
        pages: res.data.pages,
      });
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  };

  const loadUsers = async () => {
    setLoading(true);
    try {
      const res = await getAdminUsers();
      setUsers(res.data.users);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  };

  const handleFilterSubmit = (e) => {
    e.preventDefault();
    loadErrors(1);
  };

  const formatDate = (iso) => {
    if (!iso) return "\u2014";
    return new Date(iso).toLocaleString();
  };

  const statusBadge = (code) => {
    if (code >= 500) return "badge badge-danger";
    if (code >= 400) return "badge badge-warning";
    return "badge";
  };

  return (
    <div>
      <SEO title="Admin" path="/admin" />
      <h2>Admin Dashboard</h2>

      {/* Stats header */}
      {stats && (
        <div className="admin-stats">
          <div className="stat-card">
            <div className="stat-number">{stats.total_users}</div>
            <div className="stat-label">Total Users</div>
          </div>
          <div className="stat-card">
            <div className="stat-number">{stats.active_subscribers}</div>
            <div className="stat-label">Active Subscribers</div>
          </div>
          <div className="stat-card">
            <div className="stat-number">{stats.errors_24h}</div>
            <div className="stat-label">Errors (24h)</div>
          </div>
          <div className="stat-card">
            <div className="stat-number">{stats.errors_7d}</div>
            <div className="stat-label">Errors (7d)</div>
          </div>
          <div className="stat-card">
            <div className="stat-number">{stats.total_reports}</div>
            <div className="stat-label">Reports Generated</div>
          </div>
        </div>
      )}

      {/* Tab navigation */}
      <div className="admin-tabs">
        <button
          className={`tab-btn ${tab === "errors" ? "active" : ""}`}
          onClick={() => setTab("errors")}
        >
          Error Logs ({stats?.errors_total || 0})
        </button>
        <button
          className={`tab-btn ${tab === "users" ? "active" : ""}`}
          onClick={() => setTab("users")}
        >
          Users ({stats?.total_users || 0})
        </button>
      </div>

      {/* Error Logs tab */}
      {tab === "errors" && (
        <div className="admin-section">
          <form className="admin-filters" onSubmit={handleFilterSubmit}>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="">All Status Codes</option>
              <option value="4xx">4xx (Client Errors)</option>
              <option value="5xx">5xx (Server Errors)</option>
            </select>
            <input
              type="text"
              placeholder="Filter by email..."
              value={emailFilter}
              onChange={(e) => setEmailFilter(e.target.value)}
            />
            <input
              type="text"
              placeholder="Filter by endpoint..."
              value={endpointFilter}
              onChange={(e) => setEndpointFilter(e.target.value)}
            />
            <button type="submit" className="btn btn-small btn-primary">
              Filter
            </button>
          </form>

          {loading ? (
            <p>Loading...</p>
          ) : errors.length === 0 ? (
            <p className="empty-state">No errors found.</p>
          ) : (
            <>
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>User</th>
                    <th>Method</th>
                    <th>Endpoint</th>
                    <th>Status</th>
                    <th>Error</th>
                  </tr>
                </thead>
                <tbody>
                  {errors.map((err) => (
                    <>
                      <tr
                        key={err.id}
                        className="clickable-row"
                        onClick={() =>
                          setExpandedError(
                            expandedError === err.id ? null : err.id
                          )
                        }
                      >
                        <td className="nowrap">{formatDate(err.created_at)}</td>
                        <td>{err.user_email || "\u2014"}</td>
                        <td>{err.method}</td>
                        <td className="mono">{err.endpoint}</td>
                        <td>
                          <span className={statusBadge(err.status_code)}>
                            {err.status_code}
                          </span>
                        </td>
                        <td className="error-preview">
                          {err.error_message?.slice(0, 100)}
                          {err.error_message?.length > 100 ? "..." : ""}
                        </td>
                      </tr>
                      {expandedError === err.id && (
                        <tr key={`${err.id}-detail`} className="error-detail-row">
                          <td colSpan="6">
                            <div className="error-detail">
                              <h4>Full Error Message</h4>
                              <pre>{err.error_message}</pre>
                              {err.request_body && (
                                <>
                                  <h4>Request Body</h4>
                                  <pre>{err.request_body}</pre>
                                </>
                              )}
                              {err.traceback && (
                                <>
                                  <h4>Traceback</h4>
                                  <pre className="traceback">
                                    {err.traceback}
                                  </pre>
                                </>
                              )}
                            </div>
                          </td>
                        </tr>
                      )}
                    </>
                  ))}
                </tbody>
              </table>

              {/* Pagination */}
              {errorsMeta.pages > 1 && (
                <div className="pagination">
                  <button
                    disabled={errorsMeta.page <= 1}
                    onClick={() => loadErrors(errorsMeta.page - 1)}
                    className="btn btn-small btn-outline"
                  >
                    Previous
                  </button>
                  <span>
                    Page {errorsMeta.page} of {errorsMeta.pages} ({errorsMeta.total} total)
                  </span>
                  <button
                    disabled={errorsMeta.page >= errorsMeta.pages}
                    onClick={() => loadErrors(errorsMeta.page + 1)}
                    className="btn btn-small btn-outline"
                  >
                    Next
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* Users tab */}
      {tab === "users" && (
        <div className="admin-section">
          {loading ? (
            <p>Loading...</p>
          ) : (
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Email</th>
                  <th>Plan</th>
                  <th>Status</th>
                  <th>Reports</th>
                  <th>Errors</th>
                  <th>Signed Up</th>
                  <th>Last Active</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id}>
                    <td>
                      {u.email}
                      {u.is_admin && (
                        <span className="badge badge-info ml-8">Admin</span>
                      )}
                      {u.is_whitelisted && (
                        <span className="badge badge-success ml-8">
                          Whitelisted
                        </span>
                      )}
                    </td>
                    <td>
                      <span className="badge">{u.plan_tier}</span>
                    </td>
                    <td>{u.subscription_status}</td>
                    <td>{u.report_count}</td>
                    <td>{u.error_count}</td>
                    <td className="nowrap">{formatDate(u.created_at)}</td>
                    <td className="nowrap">{formatDate(u.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
