import { useEffect, useState } from "react";
import { getBillingPrices, createCheckout } from "../services/api";

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
      <div className="pricing-header">
        <h1>Choose Your Plan</h1>
        <p className="pricing-subtitle">
          Select a plan to unlock all of Case Raft's reporting features.
        </p>
        <div className="pricing-badge">🎉 50% off your first month on all plans</div>
      </div>

      <div className="pricing-grid">
        {plans.map((plan) => (
          <div
            key={plan.tier}
            className={`pricing-card ${plan.tier === "team" ? "pricing-card-featured" : ""} ${isCurrentPlan(plan.tier) ? "pricing-card-current" : ""}`}
          >
            {plan.tier === "team" && <div className="pricing-popular">Most Popular</div>}
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
                <li key={i}>✓ {f}</li>
              ))}
            </ul>
            {isCurrentPlan(plan.tier) ? (
              <button className="btn btn-outline btn-large pricing-btn" disabled>
                Current Plan
              </button>
            ) : (
              <button
                className={`btn btn-large pricing-btn ${plan.tier === "team" ? "btn-accent" : "btn-primary"}`}
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
  );
}
