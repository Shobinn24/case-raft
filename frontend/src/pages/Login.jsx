import { getLoginUrl } from "../services/api";

export default function Login() {
  return (
    <div className="login-page">
      <div className="login-card">
        <h1>Case Raft</h1>
        <p>Generate professional case reports from your Clio data.</p>
        <a href={getLoginUrl()} className="btn btn-primary">
          Sign in with Clio
        </a>
      </div>
    </div>
  );
}
