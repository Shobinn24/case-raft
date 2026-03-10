import { useEffect, useState } from "react";
import { BrowserRouter, Routes, Route, Navigate, NavLink } from "react-router-dom";
import { getAuthStatus, logout } from "./services/api";
import Login from "./pages/Login";
import Cases from "./pages/Cases";
import CaseDetail from "./pages/CaseDetail";
import FirmProductivity from "./pages/FirmProductivity";
import History from "./pages/History";

function App() {
  const [auth, setAuth] = useState({ checked: false, user: null });

  useEffect(() => {
    getAuthStatus()
      .then((res) => setAuth({ checked: true, user: res.data.user }))
      .catch(() => setAuth({ checked: true, user: null }));
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

  return (
    <div className="app">
      <nav className="navbar">
        <div className="nav-brand">Case Raft</div>
        <div className="nav-links">
          <NavLink to="/cases">Cases</NavLink>
          <NavLink to="/firm-reports">Firm Reports</NavLink>
          <NavLink to="/history">History</NavLink>
        </div>
        <div className="nav-user">
          <span>{auth.user.email}</span>
          <button onClick={handleLogout} className="btn btn-small btn-outline">
            Logout
          </button>
        </div>
      </nav>
      <main className="main-content">
        <Routes>
          <Route path="/cases" element={<Cases />} />
          <Route path="/cases/:caseId" element={<CaseDetail />} />
          <Route path="/firm-reports" element={<FirmProductivity />} />
          <Route path="/history" element={<History />} />
          <Route path="*" element={<Navigate to="/cases" replace />} />
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
