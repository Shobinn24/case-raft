import { useEffect, useState } from "react";
import { getBillingPrices, createCheckout } from "../services/api";

const TIER_ICONS = {
  solo: (
    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
  ),
  team: (
    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
      <path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  ),
  firm: (
    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="7" width="20" height="14" rx="2" ry="2" />
      <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
      <line x1="6" y1="11" x2="6" y2="11" />
      <line x1="10" y1="11" x2="10" y2="11" />
      <line x1="14" y1="11" x2="14" y2="11" />
      <line x1="18" y1="11" x2="18" y2="11" />
    </svg>
  ),
};

export default function Pricing({ user }) {
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [checkoutLoading, setCheckoutLoading] = useState(null);

  useEffect(() => {
    getBillingPrices()
      .then((res) => setPlans(res.data.plans))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

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

  if (loading) return <div className="loading">Loading plans...</div>;

  const isCurrentPlan = (tier) => user?.plan_tier === tier && user?.is_paid;

  return (
    <div className="pricing-page">
      <div className="pricing-hero">
        <div className="pricing-hero-inner">
          <div className="pricing-badge">🎉 50% off your first month</div>
          <h1>Simple, Transparent Pricing</h1>
          <p className="pricing-subtitle">
            Professional Clio reporting tools for every firm size.<br />
            No contracts. Cancel anytime.
          </p>
        </div>
      </div>

      <div className="pricing-cards-wrapper">
        <div className="pricing-grid">
          {plans.map((plan) => (
            <div
              key={plan.tier}
              className={`pricing-card ${plan.tier === "team" ? "pricing-card-featured" : ""} ${isCurrentPlan(plan.tier) ? "pricing-card-current" : ""}`}
            >
              {plan.tier === "team" && <div className="pricing-popular">Most Popular</div>}
              <div className="pricing-card-icon">{TIER_ICONS[plan.tier]}</div>
              <div className="pricing-card-header">
                <h3>{plan.name}</h3>
                <div className="pricing-amount">
                  <span className="pricing-dollar">$</span>
                  <span className="pricing-value">{plan.price}</span>
                  <span className="pricing-period">/mo</span>
                </div>
                <p className="pricing-desc">{plan.description}</p>
              </div>
              <ul className="pricing-features">
                {plan.features.map((f, i) => (
                  <li key={i}>
                    <span className="pricing-check">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                    </span>
                    {f}
                  </li>
                ))}
              </ul>
              {isCurrentPlan(plan.tier) ? (
                <button className="btn btn-outline btn-large pricing-btn" disabled>
                  Current Plan
                </button>
              ) : (
                <button
                  className={`btn btn-large pricing-btn ${plan.tier === "team" ? "pricing-btn-featured" : "btn-primary"}`}
                  onClick={() => handleSelectPlan(plan.tier)}
                  disabled={checkoutLoading === plan.tier}
                >
                  {checkoutLoading === plan.tier ? "Redirecting..." : "Get Started"}
                </button>
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="pricing-trust">
        <div className="pricing-trust-inner">
          <div className="pricing-trust-item">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" />
            </svg>
            <span>256-bit SSL encryption</span>
          </div>
          <div className="pricing-trust-item">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
            <span>Powered by Stripe</span>
          </div>
          <div className="pricing-trust-item">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="20 6 9 17 4 12" />
            </svg>
            <span>Cancel anytime</span>
          </div>
        </div>
      </div>
    </div>
  );
}
