import { useEffect, useState } from "react";
import { BrowserRouter, Routes, Route, Navigate, NavLink } from "react-router-dom";
import { getAuthStatus, logout } from "./services/api";
import Login from "./pages/Login";
import Cases from "./pages/Cases";
import CaseDetail from "./pages/CaseDetail";
import FirmProductivity from "./pages/FirmProductivity";
import History from "./pages/History";
import Pricing from "./pages/Pricing";
import Billing from "./pages/Billing";
import logo from "./assets/caseraftlogo.jpg";

function App() {
  const [auth, setAuth] = useState({ checked: false, user: null });

  const refreshAuth = () => {
    getAuthStatus()
      .then((res) => setAuth({ checked: true, user: res.data.user }))
      .catch(() => setAuth({ checked: true, user: null }));
  };

  useEffect(() => {
    refreshAuth();
  }, []);

  const handleLogout = async () => {
    await logout();
    setAuth({ checked: true, user: null });
  };

  if (!auth.checked) {
    return <div className="loading">Loading...</div>;
  }

  if (!auth.user) {
    return <Login />;
  }

  // If user has no active subscription, show pricing page
  const needsSubscription = !auth.user.is_paid;

  return (
    <div className="app">
      <nav className="navbar">
        <div className="nav-brand">
          <img src={logo} alt="Case Raft" className="nav-logo" />
        </div>
        <div className="nav-links">
          {!needsSubscription && (
            <>
              <NavLink to="/cases">Cases</NavLink>
              <NavLink to="/firm-reports">Firm Reports</NavLink>
              <NavLink to="/history">History</NavLink>
            </>
          )}
          <NavLink to="/pricing">Pricing</NavLink>
          {auth.user.is_paid && <NavLink to="/billing">Billing</NavLink>}
        </div>
        <div className="nav-user">
          {auth.user.is_paid && (
            <span className="nav-plan-badge">{auth.user.plan_tier}</span>
          )}
          <span>{auth.user.email}</span>
          <button onClick={handleLogout} className="btn btn-small btn-outline-nav">
            Logout
          </button>
        </div>
      </nav>
      <main className="main-content">
        <Routes>
          {needsSubscription ? (
            <>
              <Route path="/pricing" element={<Pricing user={auth.user} />} />
              <Route path="/billing" element={<Billing user={auth.user} onRefreshAuth={refreshAuth} />} />
              <Route path="*" element={<Navigate to="/pricing" replace />} />
            </>
          ) : (
            <>
              <Route path="/cases" element={<Cases />} />
              <Route path="/cases/:caseId" element={<CaseDetail />} />
              <Route path="/firm-reports" element={<FirmProductivity />} />
              <Route path="/history" element={<History />} />
              <Route path="/pricing" element={<Pricing user={auth.user} />} />
              <Route path="/billing" element={<Billing user={auth.user} onRefreshAuth={refreshAuth} />} />
              <Route path="*" element={<Navigate to="/cases" replace />} />
            </>
          )}
        </Routes>
      </main>
    </div>
  );
}

export default function Root() {
  return (
    <BrowserRouter>
      <App />
    </BrowserRouter>
  );
}
