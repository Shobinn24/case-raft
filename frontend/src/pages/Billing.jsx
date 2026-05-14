import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { getSubscription, createPortal, createCheckout } from "../services/api";
import SEO from "../components/SEO";

const TIER_LABELS = { free: "Free", solo: "Solo", team: "Team", firm: "Firm" };
const STATUS_LABELS = {
  free: "No active subscription",
  active: "Active",
  past_due: "Past Due — update payment method",
  canceled: "Canceled",
};

export default function Billing({ user, onRefreshAuth }) {
  const [sub, setSub] = useState(null);
  const [loading, setLoading] = useState(true);
  const [portalLoading, setPortalLoading] = useState(false);
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const justSubscribed = searchParams.get("status") === "success";
  // Tier passed through the OAuth callback after a brand-new signup from
  // the landing page. When present, auto-launch Stripe checkout so the
  // customer goes straight to payment instead of seeing an empty app.
  const autoCheckoutTier = searchParams.get("start_checkout");

  useEffect(() => {
    // If they just subscribed, refresh auth state so navbar updates
    if (justSubscribed && onRefreshAuth) onRefreshAuth();

    getSubscription()
      .then((res) => setSub(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  // Auto-start Stripe checkout for freshly signed-up users.
  useEffect(() => {
    if (!autoCheckoutTier) return;
    if (!["solo", "team", "firm"].includes(autoCheckoutTier)) return;
    // Don't re-charge someone who already has an active plan.
    if (user?.is_paid) {
      setSearchParams({}, { replace: true });
      return;
    }
    (async () => {
      try {
        const res = await createCheckout(autoCheckoutTier);
        window.location.href = res.data.checkout_url;
      } catch (err) {
        alert(err.response?.data?.error || "Failed to start checkout. Please pick a plan below.");
        setSearchParams({}, { replace: true });
      }
    })();
  }, [autoCheckoutTier, user?.is_paid, setSearchParams]);

  const handleManage = async () => {
    setPortalLoading(true);
    try {
      const res = await createPortal();
      window.location.href = res.data.portal_url;
    } catch {
      alert("Failed to open billing portal");
      setPortalLoading(false);
    }
  };

  if (loading) return <div className="loading">Loading billing info...</div>;
  if (autoCheckoutTier && !user?.is_paid) {
    return <div className="loading">Redirecting you to secure Stripe checkout...</div>;
  }

  return (
    <div className="billing-page">
      <SEO title="Billing" description="Manage your Case Raft subscription and billing." path="/billing" />
      <h1>Billing & Subscription</h1>

      {justSubscribed && (
        <div className="billing-success">
          🎉 Welcome! Your subscription is now active. You have full access to all features.
        </div>
      )}

      <div className="billing-card">
        <div className="billing-row">
          <span className="billing-label">Current Plan</span>
          <span className="billing-value billing-tier">
            {TIER_LABELS[sub?.plan_tier] || "Free"}
          </span>
        </div>
        <div className="billing-row">
          <span className="billing-label">Status</span>
          <span className={`billing-value billing-status billing-status-${sub?.subscription_status}`}>
            {STATUS_LABELS[sub?.subscription_status] || "Free"}
          </span>
        </div>
      </div>

      <div className="billing-actions">
        {sub?.is_paid ? (
          <button
            className="btn btn-primary btn-large"
            onClick={handleManage}
            disabled={portalLoading}
          >
            {portalLoading ? "Opening..." : "Manage Subscription"}
          </button>
        ) : (
          <button
            className="btn btn-accent btn-large"
            onClick={() => navigate("/pricing")}
          >
            Upgrade Now
          </button>
        )}
      </div>

      {sub?.subscription_status === "past_due" && (
        <div className="billing-warning">
          ⚠️ Your payment failed. Please update your payment method to avoid losing access.
          <button className="btn btn-small btn-accent" onClick={handleManage} style={{ marginLeft: 12 }}>
            Update Payment
          </button>
        </div>
      )}
    </div>
  );
}
