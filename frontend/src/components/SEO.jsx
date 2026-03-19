import { Helmet } from "react-helmet-async";

const DEFAULTS = {
  siteName: "Case Raft",
  description:
    "Generate court-ready PDF reports from your Clio Manage data. Case summaries, billing reports, and firm productivity — built for solo and small firm attorneys.",
  url: "https://caseraft.com",
  image: "https://caseraft.com/caseraftlogo.jpg",
};

export default function SEO({ title, description, path }) {
  const pageTitle = title
    ? `${title} | ${DEFAULTS.siteName}`
    : `${DEFAULTS.siteName} | Court-Ready Reports from Clio`;
  const pageDescription = description || DEFAULTS.description;
  const pageUrl = path ? `${DEFAULTS.url}${path}` : DEFAULTS.url;

  return (
    <Helmet>
      <title>{pageTitle}</title>
      <meta name="description" content={pageDescription} />
      <link rel="canonical" href={pageUrl} />

      <meta property="og:title" content={pageTitle} />
      <meta property="og:description" content={pageDescription} />
      <meta property="og:url" content={pageUrl} />

      <meta name="twitter:title" content={pageTitle} />
      <meta name="twitter:description" content={pageDescription} />
      <meta name="twitter:url" content={pageUrl} />
    </Helmet>
  );
}
