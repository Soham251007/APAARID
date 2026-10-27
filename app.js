// APAAR Data Integrity Portal — Multi-Tier Administrator Client
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];

// Session State
let currentRole = "institution"; // "institution" | "university" | "admin"
let currentScope = {
  type: "institution",
  name: "K J Somaiya Institute of Technology",
  university: "University of Mumbai"
};
let currentPage = "overview";
let studentPage = 1;
let studentSearchDebounce = null;
let cachedInstitutions = [];
let cachedUniversities = [];

const initials = name => (name || "NA").split(" ").filter(Boolean).map(x => x[0]).slice(0, 2).join("").toUpperCase();
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const statusClass = s => ({ Verified: "verified", Pending: "pending", Flagged: "flagged", Review: "review" })[s] || "review";

const stat = (label, value, icon, color, foot) => `
  <div class="stat-card">
    <div class="stat-top">${label}<span class="stat-icon ${color}">${icon}</span></div>
    <div class="stat-number">${value}</div>
    <div class="stat-foot">${foot}</div>
  </div>`;

function tablePanel(title, sub, rows, headers, action = "") {
  return `
    <div class="panel">
      <div class="panel-head">
        <div><h3>${title}</h3><p>${sub}</p></div>
        ${action}
      </div>
      <div class="table-wrap">
        <table>
          <thead><tr>${headers.map(h => `<th>${h}</th>`).join("")}</tr></thead>
          <tbody>${rows || `<tr><td colspan="${headers.length}"><div class="empty-state">No matching records found.</div></td></tr>`}</tbody>
        </table>
      </div>
    </div>`;
}

function toast(msg, error = false) {
  const n = document.createElement("div");
  n.className = "toast" + (error ? " error" : "");
  n.textContent = msg;
  $("#toastRoot").appendChild(n);
  setTimeout(() => n.remove(), 3500);
}

// -------------------------------------------------------------
// Data Preloaders & Scope Helpers
// -------------------------------------------------------------
async function loadMetadata() {
  try {
    const [instRes, uniRes] = await Promise.all([
      fetch("/api/institutions"),
      fetch("/api/universities")
    ]);
    const instData = await instRes.json();
    const uniData = await uniRes.json();
    cachedInstitutions = instData.institutions || [];
    cachedUniversities = uniData.universities || [];
    populateLoginDropdowns();
  } catch (err) {
    console.error("Failed to preload metadata:", err);
  }
}

function populateLoginDropdowns() {
  const instSelect = $("#loginInstituteSelect");
  if (instSelect) {
    instSelect.innerHTML = cachedInstitutions.map(i => `
      <option value="${esc(i.name)}" ${i.name.includes("Somaiya") ? "selected" : ""}>
        ${esc(i.name)} (${esc(i.code)}) · ${esc(i.university)}
      </option>
    `).join("");
  }

  const uniSelect = $("#loginUniversitySelect");
  if (uniSelect) {
    uniSelect.innerHTML = cachedUniversities.map(u => `
      <option value="${esc(u.name)}" ${u.name.includes("Mumbai") ? "selected" : ""}>
        ${esc(u.name)} (${u.college_count} colleges · ${u.student_count.toLocaleString()} students)
      </option>
    `).join("");
  }
}

function getScopeQuery() {
  if (currentScope.type === "institution" && currentScope.name) {
    return `institution=${encodeURIComponent(currentScope.name)}`;
  }
  if (currentScope.type === "university" && currentScope.name) {
    return `university=${encodeURIComponent(currentScope.name)}`;
  }
  return "";
}

async function refreshGlobalBadges() {
  try {
    const query = getScopeQuery();
    const url = `/api/overview${query ? "?" + query : ""}`;
    const res = await fetch(url);
    const data = await res.json();

    if ($("#navStudentCount")) $("#navStudentCount").textContent = data.total_student_records.toLocaleString();
    if ($("#navValidationCount")) $("#navValidationCount").textContent = data.open_anomalies.toLocaleString();
    if ($("#navDuplicateCount")) $("#navDuplicateCount").textContent = data.duplicate_candidates.toLocaleString();
    return data;
  } catch (e) {
    console.error("Failed to refresh badges:", e);
  }
}

function updateTopAndSidebarHeaders() {
  const isInst = currentScope.type === "institution";
  const isUni = currentScope.type === "university";

  const scopeTitle = isInst ? currentScope.name : (isUni ? currentScope.name : "National AICTE Central HQ");
  const roleTitle = isInst ? "Institute Administrator" : (isUni ? "University Administrator" : "AICTE Central Administrator");
  const avatarText = isInst ? initials(currentScope.name) : (isUni ? "UN" : "AI");

  if ($("#userName")) $("#userName").textContent = scopeTitle;
  if ($("#userRole")) $("#userRole").textContent = roleTitle;
  if ($("#avatar")) $("#avatar").textContent = avatarText;
  if ($("#scopePill")) $("#scopePill").innerHTML = `<span class="dot"></span> ${esc(scopeTitle)}`;
  if ($("#sidebarScopeLabel")) $("#sidebarScopeLabel").textContent = isInst ? "INSTITUTE WORKSPACE" : (isUni ? "UNIVERSITY WORKSPACE" : "AICTE WORKSPACE");
  if ($("#sidebarDbDesc")) $("#sidebarDbDesc").textContent = isInst ? `Filtered to ${esc(currentScope.name)}` : (isUni ? `Filtered to ${esc(currentScope.name)}` : "All technical universities");
}

// -------------------------------------------------------------
// 1. Overview Page (Completely Clean & Verification-Focused)
// -------------------------------------------------------------
async function renderOverview() {
  const root = $("#pageContent");
  root.innerHTML = `<div class="empty-state"><div style="font-size:26px">⏳</div>Loading live verification dashboard...</div>`;

  try {
    const query = getScopeQuery();
    const url = `/api/overview${query ? "?" + query : ""}`;
    const res = await fetch(url);
    const data = await res.json();

    if ($("#navStudentCount")) $("#navStudentCount").textContent = data.total_student_records.toLocaleString();
    if ($("#navValidationCount")) $("#navValidationCount").textContent = data.open_anomalies.toLocaleString();
    if ($("#navDuplicateCount")) $("#navDuplicateCount").textContent = data.duplicate_candidates.toLocaleString();

    const isInst = currentScope.type === "institution";
    const scopeLabel = isInst ? "In this institute" : (currentScope.type === "university" ? "Under this university" : "National Registry");

    const studentRowsHtml = (data.recent_students || []).map(s => `
      <tr>
        <td>
          <div class="student-name">
            <div class="student-avatar">${initials(s.name)}</div>
            <div><strong>${esc(s.name)}</strong><small>${esc(s.id)}</small></div>
          </div>
        </td>
        <td><strong>${esc(s.apaar)}</strong></td>
        <td>${esc(s.institution)}</td>
        <td>${esc(s.course)} (Sem ${s.semester})</td>
        <td><span class="status ${statusClass(s.status)}">${esc(s.status)}</span></td>
        <td><button class="link-btn" onclick="lookupAndOpenStudent('${s.apaar}')">Verify →</button></td>
      </tr>
    `).join("");

    const b = data.breakdown || { aadhaar_mismatch: 0, semester_leap: 0, dual_claims: 0, degree_gaps: 0 };
    const hasAnomalies = data.open_anomalies > 0;

    root.innerHTML = `
      <div class="stats-grid">
        ${stat("STUDENT RECORDS", data.total_student_records.toLocaleString(), "♙", "blue", `<span class="positive">${scopeLabel}</span>`)}
        ${stat("VERIFIED CLEAN", data.verified_percentage, "✓", "green", '<span class="positive">Identity & credentials confirmed</span>')}
        ${stat("OPEN ANOMALIES", data.open_anomalies.toLocaleString(), "⚑", hasAnomalies ? "red" : "green", hasAnomalies ? "Flagged by Random Forest model" : "All records verified")}
        ${stat("DUPLICATE CLAIMS", data.duplicate_candidates.toLocaleString(), "⧉", data.duplicate_candidates > 0 ? "amber" : "blue", "Concurrent institutional claims")}
      </div>

      <div class="dashboard-grid">
        <div class="panel">
          <div class="panel-head">
            <div>
              <h3>Random Forest Anomaly Detection Breakdown</h3>
              <p>Active detection signals audited against the Ground Truth database</p>
            </div>
            <span class="status verified">ML Model Active</span>
          </div>
          <div class="summary-cards" style="grid-template-columns: repeat(2, 1fr); gap: 12px; margin-top: 5px;">
            <div class="summary-box" style="padding: 14px">
              <span class="small-label">IDENTITY / AADHAAR MISMATCHES</span>
              <strong style="font-size: 20px; color: ${b.aadhaar_mismatch > 0 ? 'var(--red)' : 'var(--navy)'}; margin: 6px 0 2px">${b.aadhaar_mismatch.toLocaleString()}</strong>
              <small class="muted" style="font-size: 9px">Aadhaar paired with mismatched student demographics</small>
            </div>
            <div class="summary-box" style="padding: 14px">
              <span class="small-label">SEMESTER ADVANCEMENT LEAPS</span>
              <strong style="font-size: 20px; color: ${b.semester_leap > 0 ? 'var(--amber)' : 'var(--navy)'}; margin: 6px 0 2px">${b.semester_leap.toLocaleString()}</strong>
              <small class="muted" style="font-size: 9px">Anomalous semester jump during 1st-year admission</small>
            </div>
            <div class="summary-box" style="padding: 14px">
              <span class="small-label">DUAL-ENROLLMENT COLLISIONS</span>
              <strong style="font-size: 20px; color: ${b.dual_claims > 0 ? 'var(--red)' : 'var(--navy)'}; margin: 6px 0 2px">${b.dual_claims.toLocaleString()}</strong>
              <small class="muted" style="font-size: 9px">Candidate claimed simultaneously by two colleges</small>
            </div>
            <div class="summary-box" style="padding: 14px">
              <span class="small-label">PREREQUISITE DEGREE GAPS</span>
              <strong style="font-size: 20px; color: ${b.degree_gaps > 0 ? 'var(--amber)' : 'var(--navy)'}; margin: 6px 0 2px">${b.degree_gaps.toLocaleString()}</strong>
              <small class="muted" style="font-size: 9px">Non-standard qualification claimed for B.Tech admission</small>
            </div>
          </div>
          ${hasAnomalies ? `
            <div style="margin-top: 15px; text-align: right">
              <button class="secondary-btn" onclick="navigate('validation')">Open Validation Queue (${data.open_anomalies}) →</button>
            </div>` : ''}
        </div>

        <div class="panel">
          <div class="panel-head">
            <div>
              <h3>Verification Status</h3>
              <p>Adherence for ${esc(currentScope.name)}</p>
            </div>
            <span class="status ${hasAnomalies ? 'pending' : 'verified'}">${hasAnomalies ? 'Attention Required' : 'Clean Registry'}</span>
          </div>
          ${hasAnomalies ? `
            <div class="queue-list">
              <div class="queue-item">
                <div class="queue-dot red">⚑</div>
                <div>
                  <strong>Action Required: Review Flags</strong>
                  <p>${data.open_anomalies} record(s) flagged by ML classifier require manual review or seat allotment confirmation.</p>
                  <small>Random Forest prediction confidence &gt; 95%</small>
                </div>
              </div>
            </div>
            <button class="primary-btn" style="width:100%; margin-top:14px" onclick="navigate('validation')">Inspect Anomaly Queue →</button>
          ` : `
            <div style="text-align: center; padding: 25px 15px">
              <div style="font-size: 32px; color: var(--green); margin-bottom: 8px">✓</div>
              <strong style="font-size: 13px; color: var(--navy); display:block">All Registered Records Verified</strong>
              <p class="muted" style="font-size: 11px; margin-top: 6px; line-height: 1.6">
                All ${data.total_student_records.toLocaleString()} students allocated to this jurisdiction have been validated against APAAR master identities with zero conflicts.
              </p>
              <button class="secondary-btn" style="margin-top: 12px" onclick="navigate('students')">Browse Student Directory →</button>
            </div>
          `}
        </div>
      </div>

      <div class="panel">
        <div class="panel-head">
          <div>
            <h3>Recent Student Admissions & Verification Status</h3>
            <p>Master records registered under ${esc(currentScope.name)}</p>
          </div>
          <button class="link-btn" onclick="navigate('students')">View all students →</button>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr><th>Student</th><th>APAAR ID</th><th>Institution</th><th>Course & Semester</th><th>Status</th><th>Verify</th></tr>
            </thead>
            <tbody>
              ${studentRowsHtml || `<tr><td colspan="6"><div class="empty-state">No students found under this jurisdiction.</div></td></tr>`}
            </tbody>
          </table>
        </div>
      </div>`;
  } catch (err) {
    root.innerHTML = `<div class="empty-state">Failed to load overview: ${esc(err.message)}</div>`;
  }
}

// -------------------------------------------------------------
// 2. Student Directory (Strictly Scoped to That Specific Institute or University)
// -------------------------------------------------------------
async function renderStudents() {
  const q = ($("#studentSearch")?.value || "").trim();
  const st = ($("#statusFilter")?.value || "").trim();

  const isInst = currentScope.type === "institution";
  const isUni = currentScope.type === "university";
  const placeholderText = isInst ? `Search students in ${currentScope.name}...` : `Search students in ${currentScope.name}...`;

  const root = $("#pageContent");
  root.innerHTML = `
    <div class="toolbar">
      <div class="search-box">
        <span>⌕</span>
        <input id="studentSearch" placeholder="${esc(placeholderText)}" value="${esc(q)}" oninput="debounceStudentSearch()">
      </div>
      <select id="statusFilter" onchange="loadStudents(1)">
        <option value="">All statuses</option>
        <option value="Verified" ${st === "Verified" ? "selected" : ""}>Verified</option>
        <option value="Flagged" ${st === "Flagged" ? "selected" : ""}>Flagged</option>
      </select>
      <button class="secondary-btn" onclick="openUploadModal()">↑ Ingest College CSV/Excel</button>
      <button class="primary-btn" onclick="openStudentModal()">＋ Add student</button>
    </div>
    <div id="studentTableContainer">
      <div class="empty-state">Loading students...</div>
    </div>`;

  loadStudents(studentPage);
}

function debounceStudentSearch() {
  clearTimeout(studentSearchDebounce);
  studentSearchDebounce = setTimeout(() => loadStudents(1), 250);
}

async function loadStudents(page = 1) {
  studentPage = page;
  const q = ($("#studentSearch")?.value || "").trim();
  const st = ($("#statusFilter")?.value || "").trim();
  const container = $("#studentTableContainer");
  if (!container) return;

  try {
    const scopeParam = getScopeQuery();
    const queryParams = [
      scopeParam,
      `q=${encodeURIComponent(q)}`,
      `status=${encodeURIComponent(st)}`,
      `page=${page}`,
      `limit=25`
    ].filter(Boolean).join("&");

    const res = await fetch(`/api/students?${queryParams}`);
    const data = await res.json();

    const rowsHtml = (data.records || []).map(s => `
      <tr>
        <td>
          <div class="student-name">
            <div class="student-avatar">${initials(s.name)}</div>
            <div><strong>${esc(s.name)}</strong><small>${esc(s.id)} · ${esc(s.gender)}</small></div>
          </div>
        </td>
        <td><strong>${esc(s.apaar)}</strong><br><small class="muted">Aadhaar: ${esc(s.aadhar)}</small></td>
        <td><strong>${esc(s.institution)}</strong><br><small class="muted">${esc(s.course)} (Sem ${s.semester})</small></td>
        <td><span class="status ${statusClass(s.status)}">${esc(s.status)}</span></td>
        <td>${esc(s.updated)}</td>
        <td>
          <div style="display:flex; gap:6px">
            <button class="link-btn" onclick="viewStudentDetails(${JSON.stringify(s).replace(/"/g, '&quot;')})">Details</button>
            <button class="link-btn" style="color:var(--ink)" onclick="openStudentEditModal(${JSON.stringify(s).replace(/"/g, '&quot;')})">✎ Edit</button>
          </div>
        </td>
      </tr>
    `).join("");

    const totalPages = Math.ceil((data.total || 0) / (data.limit || 25));
    const isInst = currentScope.type === "institution";
    const headerTitle = isInst ? `Enrolled Students · ${esc(currentScope.name)}` : `Enrolled Students · ${esc(currentScope.name)}`;

    const paginationHtml = `
      <div style="display:flex; justify-content:space-between; align-items:center; margin-top:14px; padding:8px 4px">
        <span class="small-label">Showing ${(page - 1) * data.limit + 1} to ${Math.min(page * data.limit, data.total)} of ${data.total.toLocaleString()} records</span>
        <div style="display:flex; gap:8px">
          <button class="secondary-btn" ${page <= 1 ? "disabled style='opacity:0.5'" : ""} onclick="loadStudents(${page - 1})">← Previous</button>
          <span style="font-size:12px; font-weight:700; align-self:center">Page ${page} / ${max(totalPages, 1)}</span>
          <button class="secondary-btn" ${page >= totalPages ? "disabled style='opacity:0.5'" : ""} onclick="loadStudents(${page + 1})">Next →</button>
        </div>
      </div>`;

    container.innerHTML = `
      ${tablePanel(headerTitle, `${data.total.toLocaleString()} persistent records in database`, rowsHtml, ["Student", "APAAR & Aadhaar", "Institution & Program", "Status", "Last updated", "Action"])}
      ${paginationHtml}
      <div class="small-label" style="margin-top:10px">Records strictly scoped to <strong>${esc(currentScope.name)}</strong>. Stored persistently in <code>ground_truth.db</code>.</div>`;

    if ($("#navStudentCount")) $("#navStudentCount").textContent = data.total.toLocaleString();
  } catch (err) {
    container.innerHTML = `<div class="empty-state">Error loading records: ${esc(err.message)}</div>`;
  }
}

// -------------------------------------------------------------
// 3. Validation Queue Page (Scoped)
// -------------------------------------------------------------
async function renderValidation() {
  const root = $("#pageContent");
  root.innerHTML = `<div class="empty-state">Loading validation queue...</div>`;

  try {
    const scopeParam = getScopeQuery();
    const url = `/api/validation-queue${scopeParam ? "?" + scopeParam : ""}`;
    const res = await fetch(url);
    const data = await res.json();

    const queue = data.queue || [];
    const aadhaarCount = queue.filter(q => q.full_detail.includes("AADHAAR")).length;
    const semesterCount = queue.filter(q => q.full_detail.includes("SEMESTER") || q.full_detail.includes("LEAP")).length;
    const dualCount = queue.filter(q => q.full_detail.includes("DUAL")).length;

    root.innerHTML = `
      <div class="stats-grid">
        ${stat("VALIDATION ISSUES", data.total.toLocaleString(), "▤", data.total > 0 ? "amber" : "green", `In ${esc(currentScope.name)}`)}
        ${stat("IDENTITY MISMATCHES", aadhaarCount.toLocaleString(), "⚑", aadhaarCount > 0 ? "red" : "blue", "Aadhaar / APAAR mismatch")}
        ${stat("SEMESTER LEAPS", semesterCount.toLocaleString(), "✎", semesterCount > 0 ? "amber" : "blue", "Non-consecutive semester jump")}
        ${stat("DUAL ENROLLMENTS", dualCount.toLocaleString(), "⧉", dualCount > 0 ? "red" : "blue", "Concurrent institute claims")}
      </div>
      <div class="panel">
        <div class="panel-head">
          <div>
            <h3>Validation Review Queue · ${esc(currentScope.name)}</h3>
            <p>Candidate records quarantined by the Scikit-Learn Random Forest model.</p>
          </div>
          <button class="secondary-btn" onclick="window.location.href='/api/export/anomalies'">↓ Export queue CSV</button>
        </div>
        ${queue.length === 0 ? `
          <div class="empty-state" style="padding: 40px">
            <div style="font-size:30px; color:var(--green)">✓</div>
            <strong style="font-size:14px; margin-top:8px; display:block">Zero Open Validation Issues</strong>
            <p class="muted" style="margin-top:4px">All student records for ${esc(currentScope.name)} have passed anomaly screening.</p>
          </div>
        ` : queue.map(item => `
          <div class="validation-row" id="valRow-${item.id}">
            <div class="val-info">
              <strong>${esc(item.issue)}</strong>
              <small>${esc(item.detail)} · APAAR: ${esc(item.apaar)}</small>
              <div style="font-size:11px; color:#c05621; margin-top:3px">${esc(item.full_detail)}</div>
            </div>
            <div class="val-actions">
              <span class="status ${item.color === 'red' ? 'flagged' : 'pending'}">${esc(item.priority)}</span>
              <button class="secondary-btn" onclick="resolveIssue(this, ${item.id})">Mark reviewed</button>
            </div>
          </div>
        `).join("")}
      </div>`;
  } catch (err) {
    root.innerHTML = `<div class="empty-state">Failed to load validation queue: ${esc(err.message)}</div>`;
  }
}

// -------------------------------------------------------------
// 4. Duplicate Enrolment Alerts Page (Scoped)
// -------------------------------------------------------------
async function renderDuplicates() {
  const root = $("#pageContent");
  root.innerHTML = `<div class="empty-state">Loading duplicate candidates...</div>`;

  try {
    const scopeParam = getScopeQuery();
    const url = `/api/duplicates${scopeParam ? "?" + scopeParam : ""}`;
    const res = await fetch(url);
    const data = await res.json();

    const dups = data.duplicates || [];
    const intraCount = dups.filter(d => d.match_signal.includes("Intra-University")).length;
    const crossCount = dups.filter(d => d.match_signal.includes("Cross-University")).length;

    const rowsHtml = dups.map(d => `
      <tr>
        <td><strong>${esc(d.group_id)}</strong></td>
        <td>${esc(d.student_name)}<br><small class="muted">APAAR: ${esc(d.apaar_id)}</small></td>
        <td><span class="status verified">${esc(d.college_a)}</span></td>
        <td><span class="status flagged">${esc(d.claim_b)}</span></td>
        <td>${esc(d.match_signal)}</td>
        <td><span class="risk-pill">${esc(d.confidence)}</span></td>
        <td><button class="primary-btn" style="padding:4px 10px; font-size:11px" onclick="openAdjudicationModal('${d.apaar_id}', '${esc(d.student_name)}', '${esc(d.college_a)}', '${esc(d.claim_b)}')">Resolve →</button></td>
      </tr>
    `).join("");

    root.innerHTML = `
      <div class="stats-grid">
        ${stat("DUAL ENROLLMENT CLAIMS", data.total.toLocaleString(), "⧉", data.total > 0 ? "red" : "green", `Affecting ${esc(currentScope.name)}`)}
        ${stat("INTRA-UNIVERSITY", intraCount.toLocaleString(), "⚑", "amber", "Collisions within same university")}
        ${stat("CROSS-UNIVERSITY", crossCount.toLocaleString(), "⌕", "blue", "Collisions across different universities")}
        ${stat("ML CONFIDENCE", "98.2%", "✓", "green", "Random Forest certainty")}
      </div>
      <div class="panel">
        <div class="panel-head">
          <div>
            <h3>Potential Duplicate Enrolments · ${esc(currentScope.name)}</h3>
            <p>Students claimed simultaneously by multiple institutions in the same admission cycle.</p>
          </div>
          <span class="status ${data.total > 0 ? 'flagged' : 'verified'}">${data.total} alerts</span>
        </div>
        <div class="table-wrap">
          <table>
            <thead><tr><th>Match group</th><th>Student (APAAR)</th><th>College Claim A</th><th>College Claim B</th><th>Match Signal</th><th>Confidence</th><th>Adjudicate</th></tr></thead>
            <tbody>${rowsHtml || `<tr><td colspan="7"><div class="empty-state">No duplicate enrollment conflicts affecting ${esc(currentScope.name)}.</div></td></tr>`}</tbody>
          </table>
        </div>
      </div>`;
  } catch (err) {
    root.innerHTML = `<div class="empty-state">Failed to load duplicates: ${esc(err.message)}</div>`;
  }
}

// -------------------------------------------------------------
// 5. Verification Desk
// -------------------------------------------------------------
function renderVerification() {
  return `
    <div class="verify-layout">
      <div class="panel">
        <div class="panel-head">
          <div>
            <h3>Student Verification Desk</h3>
            <p>Real-time ML verification querying Ground Truth and active submissions.</p>
          </div>
          <span class="status review">Random Forest Model</span>
        </div>
        <form id="verifyForm">
          <div class="form-field" style="margin-bottom:15px">
            <label>Search Identifier</label>
            <select id="verifyType">
              <option value="apaar">APAAR ID (12 digits)</option>
              <option value="aadhar">Aadhaar Number</option>
              <option value="id">Student Record ID (AP-2026-XXXX)</option>
              <option value="name">Legal Student Name</option>
            </select>
          </div>
          <div class="form-field">
            <label>Identifier Value</label>
            <input id="verifyValue" placeholder="e.g. 186068428480" required>
          </div>
          <button class="primary-btn" style="margin-top:17px" type="submit">Run Real-Time ML Verification →</button>
        </form>
        <div style="margin-top:24px; padding-top:18px; border-top:1px solid var(--line)">
          <div class="small-label" style="margin-bottom:12px">QUICK TEST EXAMPLES</div>
          <button class="secondary-btn" onclick="runVerifyDirect('apaar', '186068428480')">Verified Example (Vidhi Shah)</button>
          <button class="secondary-btn" onclick="runVerifyDirect('id', 'AP-2026-0361')">Dual Enrollment Example</button>
        </div>
      </div>
      <div id="verifyResult" class="panel">
        <div class="panel-head">
          <div><h3>Verification Result</h3><p>Results evaluated live via Scikit-Learn model</p></div>
        </div>
        <div class="empty-state">
          <div style="font-size:30px; margin-bottom:10px">⌕</div>
          Enter an APAAR ID, Aadhaar number, or student record ID to evaluate.
        </div>
      </div>
    </div>
    <div class="panel" style="margin-top:0">
      <div class="panel-head"><div><h3>Verification Pipeline Checks</h3><p>Evaluated synchronously against Ground Truth.</p></div></div>
      <div class="summary-cards">
        <div class="summary-box"><strong>01</strong><span>Identity Binding & Aadhaar-APAAR pairing match</span></div>
        <div class="summary-box"><strong>02</strong><span>Prerequisite degree hierarchy & semester jump check</span></div>
        <div class="summary-box"><strong>03</strong><span>Cross-University & Intra-University dual enrollment audit</span></div>
      </div>
    </div>`;
}

async function runVerifyDirect(type, val) {
  $("#verifyType").value = type;
  $("#verifyValue").value = val;
  executeVerification(type, val);
}

async function executeVerification(type, value) {
  const target = $("#verifyResult");
  if (!target) return;
  target.innerHTML = `<div class="empty-state">Evaluating identifier through Random Forest model...</div>`;

  try {
    const res = await fetch("/api/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ type, value }),
    });
    const result = await res.json();

    const isMatch = result.match;
    const isClean = result.status === "Verified";
    const header = `
      <div class="panel-head">
        <div><h3>Verification Result</h3><p>Evaluated on ${new Date().toLocaleTimeString()}</p></div>
        <span class="status ${isClean ? 'verified' : (isMatch ? 'flagged' : 'review')}">${esc(result.status)}</span>
      </div>`;

    if (isMatch) {
      target.innerHTML = header + `
        <div class="verify-result">
          <h3>${esc(result.name)}</h3>
          <p>${isClean ? 'Student identity successfully confirmed in master registry with zero anomalies.' : 'ANOMALY DETECTED: This record triggered institutional review flags.'}</p>
          <div class="result-row"><span>Student Record ID</span><strong>${esc(result.id)}</strong></div>
          <div class="result-row"><span>APAAR ID</span><strong>${esc(result.apaar)}</strong></div>
          <div class="result-row"><span>Aadhaar Binding</span><strong>${esc(result.aadhar)}</strong></div>
          <div class="result-row"><span>Enrolled Institution</span><strong>${esc(result.institution)}</strong></div>
          <div class="result-row"><span>Affiliating University</span><strong>${esc(result.university)}</strong></div>
          <div class="result-row"><span>Course & Semester</span><strong>${esc(result.course)} (Semester ${result.semester})</strong></div>
          <div class="result-row"><span>Anomaly Risk Score</span><strong><span class="risk-pill" style="background:${isClean ? '#e6fffa;color:#234e52' : '#fed7d7;color:#9b2c2c'}">${(result.risk_score * 100).toFixed(1)}% Risk</span></strong></div>
          <div class="result-row"><span>Integrity Audit</span><strong>${esc(result.conflict_details)}</strong></div>
        </div>`;
    } else {
      target.innerHTML = header + `
        <div class="empty-state">
          <div style="font-size:27px; margin-bottom:10px">⌕</div>
          <strong>${esc(result.message)}</strong>
          <p>Please double check the entered value or verify whether the student was officially registered in the Ground Truth database.</p>
        </div>`;
    }
  } catch (err) {
    target.innerHTML = `<div class="empty-state">Verification lookup failed: ${esc(err.message)}</div>`;
  }
}

// -------------------------------------------------------------
// 6. Reports & Exports Page
// -------------------------------------------------------------
async function renderReports() {
  const root = $("#pageContent");
  root.innerHTML = `<div class="empty-state">Loading report metrics...</div>`;

  try {
    const query = getScopeQuery();
    const res = await fetch(`/api/overview${query ? "?" + query : ""}`);
    const data = await res.json();

    root.innerHTML = `
      <div class="stats-grid">
        ${stat("TOTAL REGISTRY ROWS", data.total_student_records.toLocaleString(), "▤", "blue", `In ${esc(currentScope.name)}`)}
        ${stat("VERIFIED RATIO", data.verified_percentage, "✓", "green", "Confirmed enrolled students")}
        ${stat("ANOMALY FLAGS", data.open_anomalies.toLocaleString(), "⚑", "amber", "Quarantined by Random Forest")}
        ${stat("PERSISTENCE STATUS", "Disk-Backed", "⌂", "green", "All changes written to SQLite")}
      </div>
      <div class="panel">
        <div class="panel-head">
          <div><h3>Export Live Database Reports</h3><p>Download genuine CSV files streamed directly from SQLite.</p></div>
        </div>
        <div class="summary-cards">
          <div class="summary-box">
            <strong>Student Master Registry</strong>
            <span>Full Ground Truth master student profiles, APAAR IDs, and academic records.</span>
            <button class="secondary-btn" style="margin-top:14px" onclick="window.location.href='/api/export/students'">↓ Download Master CSV</button>
          </div>
          <div class="summary-box">
            <strong>Institution Directory</strong>
            <span>AICTE recognized institutions, codes, and university affiliations.</span>
            <button class="secondary-btn" style="margin-top:14px" onclick="window.location.href='/api/export/institutions'">↓ Download Institutions CSV</button>
          </div>
          <div class="summary-box">
            <strong>Anomaly & Validation Queue</strong>
            <span>Full audit log of Random Forest flagged records and duplicate conflicts.</span>
            <button class="secondary-btn" style="margin-top:14px" onclick="window.location.href='/api/export/anomalies'">↓ Download Anomalies CSV</button>
          </div>
        </div>
      </div>
      <div class="panel">
        <h3 style="font:800 14px Manrope">Database Persistence Guarantee</h3>
        <p class="muted" style="line-height:1.8; font-size:12px">
          All student records and validation logs are saved directly to disk in <code>database/ground_truth.db</code> and <code>database/college_submissions.db</code>. When you add new students or ingest batches, they are permanently saved. Nothing is wiped or reset on refresh or restart.
        </p>
      </div>`;
  } catch (err) {
    root.innerHTML = `<div class="empty-state">Failed to load reports: ${esc(err.message)}</div>`;
  }
}

// -------------------------------------------------------------
// Modals & Profile Switching
// -------------------------------------------------------------
function openModal(title, body, onSave, saveLabel = "Save record") {
  const root = $("#modalRoot");
  root.innerHTML = `
    <div class="modal-backdrop" id="modalBackdrop">
      <div class="modal">
        <div class="modal-head">
          <h2>${title}</h2>
          <button class="modal-close" onclick="closeModal()">×</button>
        </div>
        <div class="modal-body">${body}</div>
        <div class="modal-foot">
          <button class="secondary-btn" onclick="closeModal()">Cancel</button>
          <button class="primary-btn" id="modalSave">${saveLabel}</button>
        </div>
      </div>
    </div>`;
  $("#modalBackdrop").addEventListener("click", e => { if (e.target.id === "modalBackdrop") closeModal(); });
  $("#modalSave").onclick = onSave;
}

function closeModal() { $("#modalRoot").innerHTML = ""; }

// Role / User Switcher Modal (Allows Instant Switching at Any Time)
function openSwitchUserModal() {
  const instOptions = cachedInstitutions.map(i => `
    <option value="${esc(i.name)}" ${currentScope.type === 'institution' && currentScope.name === i.name ? 'selected' : ''}>
      ${esc(i.name)} (${esc(i.code)}) · ${esc(i.university)}
    </option>
  `).join("");

  const uniOptions = cachedUniversities.map(u => `
    <option value="${esc(u.name)}" ${currentScope.type === 'university' && currentScope.name === u.name ? 'selected' : ''}>
      ${esc(u.name)} (${u.college_count} colleges)
    </option>
  `).join("");

  openModal("Switch Administrator Profile", `
    <form id="switchUserForm">
      <div class="form-field" style="margin-bottom:14px">
        <label>Administrative Tier</label>
        <select id="modalRoleSelect" onchange="toggleModalSwitchRoleFields()">
          <option value="institution" ${currentRole === 'institution' ? 'selected' : ''}>Institute Administrator</option>
          <option value="university" ${currentRole === 'university' ? 'selected' : ''}>University Administrator</option>
          <option value="admin" ${currentRole === 'admin' ? 'selected' : ''}>AICTE Central Administrator</option>
        </select>
      </div>

      <div class="form-field ${currentRole === 'institution' ? '' : 'hidden'}" id="modalInstWrap" style="margin-bottom:14px">
        <label>Select Institute</label>
        <select id="modalInstSelect">${instOptions}</select>
      </div>

      <div class="form-field ${currentRole === 'university' ? '' : 'hidden'}" id="modalUniWrap" style="margin-bottom:14px">
        <label>Select University</label>
        <select id="modalUniSelect">${uniOptions}</select>
      </div>

      <p class="small-label" style="margin-top:12px">
        Switching profile immediately updates the student records, validation queue, and overview metrics to match your selected jurisdiction.
      </p>
    </form>`, () => {
    const roleVal = $("#modalRoleSelect").value;
    if (roleVal === "institution") {
      const selectedInst = $("#modalInstSelect").value;
      currentRole = "institution";
      currentScope = { type: "institution", name: selectedInst };
    } else if (roleVal === "university") {
      const selectedUni = $("#modalUniSelect").value;
      currentRole = "university";
      currentScope = { type: "university", name: selectedUni };
    } else {
      currentRole = "admin";
      currentScope = { type: "admin", name: "AICTE Central HQ" };
    }

    closeModal();
    updateTopAndSidebarHeaders();
    refreshGlobalBadges();
    toast(`Switched workspace to ${currentScope.name}`);
    render();
  }, "Apply & Switch Workspace");
}

function toggleModalSwitchRoleFields() {
  const r = $("#modalRoleSelect").value;
  $("#modalInstWrap").classList.toggle("hidden", r !== "institution");
  $("#modalUniWrap").classList.toggle("hidden", r !== "university");
}

async function openStudentModal() {
  const isInst = currentScope.type === "institution";
  const instOptions = cachedInstitutions.map(i => `
    <option value="${esc(i.name)}" ${isInst && i.name === currentScope.name ? "selected" : ""}>
      ${esc(i.name)} (${esc(i.code)})
    </option>
  `).join("");

  openModal("Add Student Record", `
    <form id="studentForm">
      <div class="form-grid">
        <div class="form-field"><label>Full Legal Name *</label><input name="name" required placeholder="Aarav Sharma"></div>
        <div class="form-field"><label>APAAR ID (12 digits) *</label><input name="apaar" required placeholder="123456789012" maxlength="12"></div>
        <div class="form-field"><label>Aadhaar Number (12 digits)</label><input name="aadhar" placeholder="Optional - auto-generated if blank" maxlength="12"></div>
        <div class="form-field"><label>Institution *</label>
          <select name="institution" required ${isInst ? "disabled" : ""}>
            ${instOptions}
          </select>
        </div>
        <div class="form-field"><label>Course Program *</label><input name="course" required value="B.Tech - Computer Engineering"></div>
        <div class="form-field"><label>Current Semester</label><select name="semester"><option value="1">Semester 1</option><option value="2">Semester 2</option><option value="3">Semester 3</option><option value="4">Semester 4</option></select></div>
        <div class="form-field"><label>Prerequisite Qualification</label><input name="last_degree" value="12th Standard / HSC"></div>
        <div class="form-field"><label>Date of Birth</label><input type="date" name="dob" value="2007-04-15"></div>
      </div>
      <p class="small-label" style="margin-top:14px">This record will be permanently saved to disk in <code>ground_truth.db</code>.</p>
    </form>`, async () => {
    const form = $("#studentForm");
    if (!form.reportValidity()) return;
    const payload = Object.fromEntries(new FormData(form));
    if (isInst) payload.institution = currentScope.name;

    try {
      const res = await fetch("/api/students", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) {
        toast(data.error || "Failed to add student.", true);
        return;
      }
      toast(data.message);
      closeModal();
      refreshGlobalBadges();
      if (currentPage === "students") loadStudents(1);
      else if (currentPage === "overview") renderOverview();
    } catch (err) {
      toast(err.message, true);
    }
  });
}

async function openStudentEditModal(s) {
  const instOptions = cachedInstitutions.map(i => `
    <option value="${esc(i.name)}" ${i.name === s.institution ? "selected" : ""}>${esc(i.name)} (${esc(i.code)})</option>
  `).join("");

  openModal(`Edit Student Record · ${esc(s.id)}`, `
    <form id="editStudentForm">
      <div class="form-grid">
        <div class="form-field"><label>Full Legal Name *</label><input name="name" required value="${esc(s.name)}"></div>
        <div class="form-field"><label>APAAR ID</label><input value="${esc(s.apaar)}" disabled style="background:#f5f7fb; opacity:0.8"></div>
        <div class="form-field"><label>Aadhaar Number</label><input value="${esc(s.aadhar)}" disabled style="background:#f5f7fb; opacity:0.8"></div>
        <div class="form-field"><label>Allocated Institution *</label>
          <select name="institution" required>
            ${instOptions}
          </select>
        </div>
        <div class="form-field"><label>Course Program *</label><input name="course" required value="${esc(s.course)}"></div>
        <div class="form-field"><label>Current Semester</label>
          <select name="semester">
            ${[1, 2, 3, 4, 5, 6, 7, 8].map(sm => `<option value="${sm}" ${Number(s.semester) === sm ? "selected" : ""}>Semester ${sm}</option>`).join("")}
          </select>
        </div>
        <div class="form-field"><label>Prerequisite Qualification</label><input name="last_degree" value="${esc(s.last_degree || '12th Standard / HSC')}"></div>
        <div class="form-field"><label>Date of Birth</label><input type="date" name="dob" value="${esc(s.dob || '2007-04-15')}"></div>
        <div class="form-field"><label>Verification Status</label>
          <select name="status">
            <option value="Verified" ${s.status === "Verified" ? "selected" : ""}>Verified</option>
            <option value="Flagged" ${s.status === "Flagged" ? "selected" : ""}>Flagged</option>
          </select>
        </div>
      </div>
      <p class="small-label" style="margin-top:14px">Updates will be committed directly to disk in <code>ground_truth.db</code>.</p>
    </form>`, async () => {
    const form = $("#editStudentForm");
    if (!form.reportValidity()) return;
    const payload = Object.fromEntries(new FormData(form));

    try {
      const res = await fetch(`/api/students/${s.numeric_id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) {
        toast(data.error || "Failed to update student.", true);
        return;
      }
      toast(data.message);
      closeModal();
      if (currentPage === "students") loadStudents(studentPage);
      else if (currentPage === "overview") renderOverview();
    } catch (err) {
      toast(err.message, true);
    }
  }, "Save Changes");
}

async function openUploadModal() {
  const isInst = currentScope.type === "institution";
  const instOptions = cachedInstitutions.map(i => `
    <option value="${esc(i.name)}" ${isInst && i.name === currentScope.name ? "selected" : ""}>${esc(i.name)}</option>
  `).join("");

  openModal("Ingest College Admission CSV / Excel", `
    <form id="uploadForm">
      <div class="form-field" style="margin-bottom:14px">
        <label>Submitting Institution</label>
        <select id="uploadCollegeSelect" name="college_name" ${isInst ? "disabled" : ""}>
          ${instOptions}
        </select>
      </div>
      <div class="form-field">
        <label>Upload File (.csv or .xlsx)</label>
        <input type="file" id="collegeFile" name="file" accept=".csv, .xlsx" required style="padding:10px">
      </div>
      <p class="small-label" style="margin-top:14px">
        Incoming records will be processed through the Scikit-Learn Random Forest model. Clean students are auto-allocated to Ground Truth; duplicates & discrepancies are quarantined.
      </p>
    </form>`, async () => {
    const fileInp = $("#collegeFile");
    if (!fileInp.files.length) {
      toast("Please select a file to upload.", true);
      return;
    }
    const formData = new FormData();
    formData.append("file", fileInp.files[0]);
    formData.append("college_name", isInst ? currentScope.name : $("#uploadCollegeSelect").value);

    toast("Processing file through Random Forest model...");
    try {
      const res = await fetch("/api/upload-csv", { method: "POST", body: formData });
      const data = await res.json();
      if (!res.ok) {
        toast(data.error || "Upload failed.", true);
        return;
      }
      closeModal();
      toast(data.message);
      refreshGlobalBadges();
      if (currentPage === "students") loadStudents(1);
      else if (currentPage === "validation") renderValidation();
      else if (currentPage === "overview") renderOverview();
    } catch (err) {
      toast(err.message, true);
    }
  }, "Run ML Ingestion");
}

function openAdjudicationModal(apaarId, name, collegeA, claimB) {
  openModal("Adjudicate Dual Admission Claim", `
    <div class="notice">
      <span class="notice-icon">i</span>
      <div>
        <strong>Dual Enrollment Conflict for ${esc(name)}</strong>
        <span>This student is concurrently claimed by two institutions in the same admission cycle.</span>
      </div>
    </div>
    <div class="result-row"><span>Student Name</span><strong>${esc(name)}</strong></div>
    <div class="result-row"><span>APAAR ID</span><strong>${esc(apaarId)}</strong></div>
    <div class="result-row"><span>College Claim A</span><strong>${esc(collegeA)}</strong></div>
    <div class="result-row"><span>College Claim B</span><strong>${esc(claimB)}</strong></div>
    <div class="form-field" style="margin-top:16px">
      <label>Confirm Official Admission to:</label>
      <select id="approvedCollegeSelect">
        <option value="${esc(collegeA)}">${esc(collegeA)}</option>
        <option value="${esc(claimB)}">${esc(claimB)}</option>
      </select>
    </div>
    <div class="form-field" style="margin-top:12px">
      <label>Verification Document / Adjudication Note</label>
      <input id="adjudicationNotes" placeholder="e.g. Verified via CAP round allotment & fee payment receipt.">
    </div>
    <p class="small-label" style="margin-top:14px">
      Clicking 'Confirm & Update Ground Truth' will officially allocate the student in <code>ground_truth.db</code> and release the other college's seat claim.
    </p>`, async () => {
    const approved = $("#approvedCollegeSelect").value;
    const notes = $("#adjudicationNotes").value || "Adjudicated by AICTE Verifier.";

    try {
      const res = await fetch("/api/resolve-duplicate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ apaar_id: apaarId, approved_college: approved, notes }),
      });
      const data = await res.json();
      if (!res.ok) {
        toast(data.error || "Adjudication failed.", true);
        return;
      }
      toast(data.message);
      closeModal();
      refreshGlobalBadges();
      renderDuplicates();
    } catch (err) {
      toast(err.message, true);
    }
  }, "Confirm & Update Ground Truth");
}

function viewStudentDetails(s) {
  openModal("Student Master Record Details", `
    <div class="result-row"><span>Full Legal Name</span><strong>${esc(s.name)}</strong></div>
    <div class="result-row"><span>Record Identifier</span><strong>${esc(s.id)}</strong></div>
    <div class="result-row"><span>APAAR ID</span><strong>${esc(s.apaar)}</strong></div>
    <div class="result-row"><span>Aadhaar Binding</span><strong>${esc(s.aadhar)}</strong></div>
    <div class="result-row"><span>Date of Birth</span><strong>${esc(s.dob)} (${esc(s.gender)})</strong></div>
    <div class="result-row"><span>Allocated Institution</span><strong>${esc(s.institution)}</strong></div>
    <div class="result-row"><span>Affiliating University</span><strong>${esc(s.university)}</strong></div>
    <div class="result-row"><span>Program & Semester</span><strong>${esc(s.course)} (Semester ${s.semester})</strong></div>
    <div class="result-row"><span>Prior Degree</span><strong>${esc(s.last_degree)}</strong></div>
    <div class="result-row"><span>Verification Status</span><strong><span class="status ${statusClass(s.status)}">${esc(s.status)}</span></strong></div>
    <div style="margin-top:18px; display:flex; justify-content:space-between; align-items:center">
      <span class="small-label">Persisted in <code>database/ground_truth.db</code>.</span>
      <button class="secondary-btn" onclick="closeModal(); openStudentEditModal(${JSON.stringify(s).replace(/"/g, '&quot;')})">✎ Edit this record</button>
    </div>
  `, () => closeModal(), "Close");
}

function lookupAndOpenStudent(apaar) {
  currentPage = "verification";
  render();
  setTimeout(() => runVerifyDirect("apaar", apaar), 100);
}

async function resolveIssue(btn, subId) {
  try {
    btn.disabled = true;
    btn.textContent = "Clearing...";
    const res = await fetch(`/api/resolve-validation/${subId}`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) {
      toast(data.error || "Failed to update review status", true);
      btn.disabled = false;
      btn.textContent = "Mark reviewed";
      return;
    }
    toast("Issue marked as reviewed and cleared from queue.");
    const row = document.getElementById(`valRow-${subId}`);
    if (row) {
      row.style.transition = "all 0.3s ease";
      row.style.opacity = "0";
      row.style.transform = "translateX(25px)";
      setTimeout(() => {
        row.remove();
        refreshGlobalBadges();
        const remaining = document.querySelectorAll(".validation-row").length;
        if (remaining === 0) {
          renderValidation();
        } else {
          const valCountElem = document.querySelector(".stats-grid .stat-card:first-child .stat-number");
          if (valCountElem) valCountElem.textContent = remaining.toLocaleString();
        }
      }, 300);
    }
  } catch (err) {
    toast("Error: " + err.message, true);
    btn.disabled = false;
    btn.textContent = "Mark reviewed";
  }
}

// -------------------------------------------------------------
// Router & Page Navigation
// -------------------------------------------------------------
const pages = {
  overview: { title: "Overview", eyebrow: "VERIFICATION OVERVIEW", desc: "Live student verification and anomaly integrity status." },
  students: { title: "Student Directory", eyebrow: "ENROLLED STUDENTS", desc: "Manage and verify student records under this jurisdiction." },
  validation: { title: "Validation Queue", eyebrow: "DATA QUALITY", desc: "Quarantined records flagged by the Random Forest classifier." },
  duplicates: { title: "Duplicate Enrolment Alerts", eyebrow: "COLLISION REVIEW", desc: "Multi-institutional admission conflicts." },
  verification: { title: "Verify a Student", eyebrow: "VERIFICATION DESK", desc: "Real-time ML verification queries against master records." },
  reports: { title: "Reports & Exports", eyebrow: "REPORTING CENTRE", desc: "Download live CSV reports streamed directly from SQLite." },
};

function render() {
  const p = pages[currentPage];
  $("#breadcrumb").textContent = p.title;
  $("#pageTitle").innerHTML = `${esc(currentScope.name)} <span>✦</span>`;
  $("#pageEyebrow").textContent = `${currentRole.toUpperCase()} · ${p.eyebrow}`;
  $("#pageDescription").textContent = p.desc;

  $$(".nav-item").forEach(b => b.classList.toggle("active", b.dataset.page === currentPage));
  $("#newRecordBtn").style.display = ["overview", "students"].includes(currentPage) ? "inline-flex" : "none";

  if (currentPage === "overview") renderOverview();
  else if (currentPage === "students") renderStudents();
  else if (currentPage === "validation") renderValidation();
  else if (currentPage === "duplicates") renderDuplicates();
  else if (currentPage === "verification") {
    $("#pageContent").innerHTML = renderVerification();
    $("#verifyForm").addEventListener("submit", e => {
      e.preventDefault();
      executeVerification($("#verifyType").value, $("#verifyValue").value.trim());
    });
  } else if (currentPage === "reports") {
    renderReports();
  }
}

function navigate(p) {
  currentPage = p;
  render();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function max(a, b) { return a > b ? a : b; }

// -------------------------------------------------------------
// Event Listeners Setup
// -------------------------------------------------------------
$("#sideNav").addEventListener("click", e => {
  const b = e.target.closest("[data-page]");
  if (b) navigate(b.dataset.page);
});

$("#newRecordBtn").addEventListener("click", openStudentModal);
$("#exportBtn").addEventListener("click", () => window.location.href = "/api/export/students");

// Topbar user switcher button & user chip
$("#switchUserBtn").addEventListener("click", openSwitchUserModal);
$("#userChipBtn").addEventListener("click", openSwitchUserModal);

// Login Role selector toggle
$("#roleSelect").addEventListener("change", e => {
  const r = e.target.value;
  $("#instituteSelectWrap").classList.toggle("hidden", r !== "institution");
  $("#universitySelectWrap").classList.toggle("hidden", r !== "university");
});

$("#loginBtn").addEventListener("click", () => {
  const r = $("#roleSelect").value;
  currentRole = r;

  if (r === "institution") {
    const instName = $("#loginInstituteSelect").value;
    currentScope = { type: "institution", name: instName };
  } else if (r === "university") {
    const uniName = $("#loginUniversitySelect").value;
    currentScope = { type: "university", name: uniName };
  } else {
    currentScope = { type: "admin", name: "AICTE Central HQ" };
  }

  $("#loginView").classList.add("hidden");
  $("#appView").classList.remove("hidden");
  updateTopAndSidebarHeaders();
  refreshGlobalBadges();
  navigate("overview");
});

$("#logoutBtn").addEventListener("click", () => {
  $("#appView").classList.add("hidden");
  $("#loginView").classList.remove("hidden");
  currentPage = "overview";
  toast("Signed out.");
});

// Expose globals for inline onclicks
window.navigate = navigate;
window.toast = toast;
window.openStudentModal = openStudentModal;
window.openStudentEditModal = openStudentEditModal;
window.openUploadModal = openUploadModal;
window.openSwitchUserModal = openSwitchUserModal;
window.toggleModalSwitchRoleFields = toggleModalSwitchRoleFields;
window.closeModal = closeModal;
window.loadStudents = loadStudents;
window.debounceStudentSearch = debounceStudentSearch;
window.viewStudentDetails = viewStudentDetails;
window.lookupAndOpenStudent = lookupAndOpenStudent;
window.resolveIssue = resolveIssue;
window.openAdjudicationModal = openAdjudicationModal;
window.runVerifyDirect = runVerifyDirect;

// Initial Load
loadMetadata().then(() => {
  if (!$("#loginView").classList.contains("hidden")) {
    // on login view
  } else {
    updateTopAndSidebarHeaders();
    refreshGlobalBadges();
    render();
  }
});
