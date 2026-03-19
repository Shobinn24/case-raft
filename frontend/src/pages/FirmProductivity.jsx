import { useState } from "react";
import { generateFirmReport, exportAccounting, getReportDownloadUrl } from "../services/api";
import SEO from "../components/SEO";

const DEFAULT_SECTIONS = {
  summary: true,
  employeeTable: true,
  utilization: true,
  realization: true,
  collection: true,
  writeOffs: true,
  aging: true,
  revenueSummary: true,
  invoiceList: true,
  revenueByPracticeArea: true,
};

const SECTION_LABELS = {
  summary: "Productivity Summary",
  employeeTable: "Employee Table",
  utilization: "Utilization Rate",
  realization: "Realization Rate",
  collection: "Collection Rate",
  writeOffs: "Write-Offs",
  aging: "AR Aging",
  revenueSummary: "Revenue Summary",
  invoiceList: "Invoice List",
  revenueByPracticeArea: "Revenue by Practice Area",
};

export default function FirmProductivity() {
  // Default to current month
  const today = new Date().toISOString().slice(0, 10);
  const firstOfMonth = new Date(
    new Date().getFullYear(),
    new Date().getMonth(),
    1
  )
    .toISOString()
    .slice(0, 10);

  const [startDate, setStartDate] = useState(firstOfMonth);
  const [endDate, setEndDate] = useState(today);
  const [generating, setGenerating] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [generatedReport, setGeneratedReport] = useState(null);
  const [error, setError] = useState(null);
  const [sections, setSections] = useState({ ...DEFAULT_SECTIONS });

  const toggleSection = (key) => {
    setSections((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const handleGenerate = async () => {
    if (!startDate || !endDate) {
      setError("Please select both a start and end date.");
      return;
    }
    setGenerating(true);
    setError(null);
    setGeneratedReport(null);
    try {
      const res = await generateFirmReport(startDate, endDate, "firm_productivity", { sections });
      setGeneratedReport(res.data.report);
    } catch (err) {
      setError(err.response?.data?.error || "Failed to generate report");
    } finally {
      setGenerating(false);
    }
  };

  const handleExportCSV = async (format) => {
    if (!startDate || !endDate) {
      setError("Please select both a start and end date.");
      return;
    }
    setExporting(true);
    setError(null);
    try {
      const res = await exportAccounting(startDate, endDate, format);
      const url = URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement("a");
      a.href = url;
      a.download = `accounting_export_${startDate}_${endDate}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.response?.data?.error || "Failed to export CSV");
    } finally {
      setExporting(false);
    }
  };

  return (
    <section>
      <SEO title="Firm Productivity Report" description="Generate firm-wide productivity reports with utilization and realization rates." path="/firm-reports" />
      <h2>Firm Productivity Report</h2>
      <p className="page-subtitle">
        Generate a report showing hours, revenue, utilization, and collection
        metrics for each employee over a selected date range.
      </p>

      <div className="detail-section">
        <h3>Select Date Range</h3>
        <div className="date-range-form">
          <label>
            Start Date
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
            />
          </label>
          <label>
            End Date
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
            />
          </label>
        </div>
      </div>

      <div className="detail-section">
        <h3>Report Sections</h3>
        <div className="section-picker">
          {Object.entries(SECTION_LABELS).map(([key, label]) => (
            <label key={key} className="section-checkbox">
              <input
                type="checkbox"
                checked={sections[key]}
                onChange={() => toggleSection(key)}
              />
              {label}
            </label>
          ))}
        </div>
      </div>

      <div className="report-actions mt-24">
        {error && <p className="error">{error}</p>}
        <div className="btn-group">
          <button
            className="btn btn-primary"
            onClick={handleGenerate}
            disabled={generating || exporting}
          >
            {generating ? "Generating..." : "Generate PDF Report"}
          </button>
          <button
            className="btn btn-secondary"
            onClick={() => handleExportCSV("quickbooks")}
            disabled={generating || exporting}
          >
            {exporting ? "Exporting..." : "Export CSV (QuickBooks)"}
          </button>
          <button
            className="btn btn-secondary"
            onClick={() => handleExportCSV("xero")}
            disabled={generating || exporting}
          >
            {exporting ? "Exporting..." : "Export CSV (Xero)"}
          </button>
        </div>

        {generatedReport && (
          <div className="report-success">
            <p>Report generated successfully!</p>
            <a
              href={getReportDownloadUrl(generatedReport.id)}
              className="btn btn-secondary"
              target="_blank"
              rel="noopener noreferrer"
            >
              Download PDF
            </a>
          </div>
        )}
      </div>
    </section>
  );
}
