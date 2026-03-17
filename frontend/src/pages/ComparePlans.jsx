import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { createCheckout } from "../services/api";

const CHECK = (
  <svg className="compare-icon compare-icon-check" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="20 6 9 17 4 12" />
  </svg>
);

const DASH = (
  <svg className="compare-icon compare-icon-dash" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="5" y1="12" x2="19" y2="12" />
  </svg>
);

const FEATURES = [
  {
    category: "Reporting",
    items: [
      { name: "Case summary reports", solo: true, team: true, firm: true },
      { name: "PDF export & download", solo: true, team: true, firm: true },
      { name: "Report download history", solo: true, team: true, firm: true },
      { name: "Firm productivity reports", solo: "Basic", team: "Full", firm: "Full" },
      { name: "Batch report generation", solo: false, team: "Up to 20", firm: "Unlimited" },
      { name: "Custom report sections", solo: false, team: false, firm: true },
    ],
  },
  {
    category: "Analytics",
    items: [
      { name: "Trust management report", solo: false, team: true, firm: true },
      { name: "Collected revenue reports", solo: false, team: true, firm: true },
      { name: "Realization & utilization rates", solo: false, team: true, firm: true },
      { name: "Write-off tracking", solo: false, team: true, firm: true },
      { name: "AR aging analysis", solo: false, team: false, firm: true },
    ],
  },
  {
    category: "Export & Integration",
    items: [
      { name: "Clio Manage integration", solo: true, team: true, firm: true },
      { name: "CSV export (QuickBooks / Xero)", solo: false, team: true, firm: true },
    ],
  },
  {
    category: "Users & Support",
    items: [
      { name: "Users included", solo: "1", team: "Up to 5", firm: "Unlimited" },
      { name: "Email support", solo: true, team: true, firm: true },
      { name: "Priority support", solo: false, team: false, firm: true },
    ],
  },
];

function CellValue({ value }) {
  if (value === true) return CHECK;
  if (value === false) return DASH;
  return <span className="compare-text-value">{value}</span>;
}

export default function ComparePlans({ user }) {
  const [checkoutLoading, setCheckoutLoading] = useState(null);
  const navigate = useNavigate();

  const handleSelectPlan = async (tier) => {
    setCheckoutLoading(tier);
    try {
      const res = await createCheckout(tier);
      window.location.href = res.data.checkout_url;
    } catch (err) {
      alert(err.response?.data?.error || "Failed to start checkout");
      setCheckoutLoading(null);
    }
  };

  const isCurrentPlan = (tier) => user?.plan_tier === tier && user?.is_paid;

  return (
    <div className="compare-page">
      <div className="compare-header">
        <Link to="/pricing" className="compare-back">&larr; Back to Pricing</Link>
        <h1>Compare Plans</h1>
        <p className="compare-subtitle">
          A detailed breakdown of every feature across all plans.<br />
          Pick the one that fits your firm.
        </p>
      </div>

      <div className="compare-table-wrapper">
        <table className="compare-table">
          <thead>
            <tr>
              <th className="compare-feature-col"></th>
              <th className="compare-plan-col">
                <div className="compare-plan-name">Solo</div>
                <div className="compare-plan-price">$29<span>/mo</span></div>
                <div className="compare-plan-desc">1 user</div>
              </th>
              <th className="compare-plan-col compare-plan-col-featured">
                <div className="compare-plan-badge">Most Popular</div>
                <div className="compare-plan-name">Team</div>
                <div className="compare-plan-price">$79<span>/mo</span></div>
                <div className="compare-plan-desc">Up to 5 users</div>
              </th>
              <th className="compare-plan-col">
                <div className="compare-plan-name">Firm</div>
                <div className="compare-plan-price">$149<span>/mo</span></div>
                <div className="compare-plan-desc">Unlimited users</div>
              </th>
            </tr>
          </thead>
          <tbody>
            {FEATURES.map((group) => (
              <>
                <tr key={group.category} className="compare-category-row">
                  <td colSpan={4}>{group.category}</td>
                </tr>
                {group.items.map((item) => (
                  <tr key={item.name} className="compare-feature-row">
                    <td className="compare-feature-name">{item.name}</td>
                    <td className="compare-cell"><CellValue value={item.solo} /></td>
                    <td className="compare-cell compare-cell-featured"><CellValue value={item.team} /></td>
                    <td className="compare-cell"><CellValue value={item.firm} /></td>
                  </tr>
                ))}
              </>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <td></td>
              <td className="compare-cta-cell">
                {isCurrentPlan("solo") ? (
                  <button className="btn btn-outline btn-small" disabled>Current Plan</button>
                ) : (
                  <button
                    className="btn btn-primary"
                    onClick={() => handleSelectPlan("solo")}
                    disabled={checkoutLoading === "solo"}
                  >
                    {checkoutLoading === "solo" ? "Redirecting..." : "Get Started"}
                  </button>
                )}
              </td>
              <td className="compare-cta-cell compare-cell-featured">
                {isCurrentPlan("team") ? (
                  <button className="btn btn-outline btn-small" disabled>Current Plan</button>
                ) : (
                  <button
                    className="btn compare-btn-featured"
                    onClick={() => handleSelectPlan("team")}
                    disabled={checkoutLoading === "team"}
                  >
                    {checkoutLoading === "team" ? "Redirecting..." : "Get Started"}
                  </button>
                )}
              </td>
              <td className="compare-cta-cell">
                {isCurrentPlan("firm") ? (
                  <button className="btn btn-outline btn-small" disabled>Current Plan</button>
                ) : (
                  <button
                    className="btn btn-primary"
                    onClick={() => handleSelectPlan("firm")}
                    disabled={checkoutLoading === "firm"}
                  >
                    {checkoutLoading === "firm" ? "Redirecting..." : "Get Started"}
                  </button>
                )}
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}
