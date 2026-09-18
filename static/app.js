// No build step, no CDN dependencies -- this tool must keep working
// with no internet access after installation (see README's
// local/offline-first requirement).

const departmentSelect = document.getElementById("department");
const letterTypeSelect = document.getElementById("letter-type");
const factsContainer = document.getElementById("facts-container");
const addFactBtn = document.getElementById("add-fact");
const form = document.getElementById("generate-form");
const generateBtn = document.getElementById("generate-btn");
const spinner = document.getElementById("spinner");
const generateError = document.getElementById("generate-error");
const draftOutput = document.getElementById("draft-output");
const autoDetectNotice = document.getElementById("auto-detect-notice");
const referencesList = document.getElementById("references-list");
const copyBtn = document.getElementById("copy-btn");
const downloadDocxBtn = document.getElementById("download-docx-btn");
const downloadPdfBtn = document.getElementById("download-pdf-btn");
const exportError = document.getElementById("export-error");

function addFactRow(key = "", value = "") {
  const row = document.createElement("div");
  row.className = "facts-row";
  row.innerHTML = `
    <input type="text" class="fact-key" placeholder="नाम, जैसे: विद्यालय" value="${escapeAttr(key)}">
    <input type="text" class="fact-value" placeholder="मान, जैसे: राजकीय मध्य विद्यालय" value="${escapeAttr(value)}">
    <button type="button" class="remove-fact">हटाएँ</button>
  `;
  row.querySelector(".remove-fact").addEventListener("click", () => row.remove());
  factsContainer.appendChild(row);
}

function escapeAttr(s) {
  return String(s).replace(/"/g, "&quot;");
}

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s;
  return div.innerHTML;
}

function collectFacts() {
  const facts = {};
  for (const row of factsContainer.querySelectorAll(".facts-row")) {
    const key = row.querySelector(".fact-key").value.trim();
    const value = row.querySelector(".fact-value").value.trim();
    if (key && value) facts[key] = value;
  }
  return facts;
}

addFactBtn.addEventListener("click", () => addFactRow());
addFactRow();

async function loadCatalog() {
  try {
    const [departments, letterTypes] = await Promise.all([
      fetch("/api/departments").then(r => r.json()),
      fetch("/api/letter-types").then(r => r.json()),
    ]);
    for (const d of departments) {
      const opt = document.createElement("option");
      opt.value = d; opt.textContent = d;
      departmentSelect.appendChild(opt);
    }
    for (const t of letterTypes) {
      const opt = document.createElement("option");
      opt.value = t; opt.textContent = t;
      letterTypeSelect.appendChild(opt);
    }
  } catch (e) {
    console.error("catalog load failed", e);
  }
}
loadCatalog();

let lastDraft = "";

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  generateError.hidden = true;
  autoDetectNotice.hidden = true;
  generateBtn.disabled = true;
  spinner.hidden = false;

  const payload = {
    request: document.getElementById("request").value,
    department: departmentSelect.value || null,
    letter_type: letterTypeSelect.value || null,
    facts: collectFacts(),
  };

  try {
    const resp = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!resp.ok) {
      const body = await resp.json().catch(() => ({}));
      throw new Error(body.detail || `त्रुटि (HTTP ${resp.status})`);
    }
    const data = await resp.json();
    lastDraft = data.draft;
    draftOutput.value = data.draft;
    copyBtn.disabled = false;
    downloadDocxBtn.disabled = false;
    downloadPdfBtn.disabled = false;

    if (data.department_auto_detected) {
      autoDetectNotice.hidden = false;
      autoDetectNotice.textContent = `विभाग स्वतः पहचाना गया: ${data.department_used}`;
    }

    renderReferences(data.references);
  } catch (err) {
    generateError.hidden = false;
    generateError.textContent = err.message || "अज्ञात त्रुटि हुई।";
  } finally {
    generateBtn.disabled = false;
    spinner.hidden = true;
  }
});

function renderReferences(references) {
  if (!references.length) {
    referencesList.innerHTML = "<p class='spinner'>कोई संदर्भ पत्र नहीं मिला।</p>";
    return;
  }
  referencesList.innerHTML = references.map(r => `
    <div class="reference-item">
      <div class="meta">
        <span class="tag">${escapeHtml(r.department || "?")}</span>
        <span class="tag">${escapeHtml(r.letter_type || "?")}</span>
        ${r.subject ? `<strong>${escapeHtml(r.subject)}</strong>` : ""}
      </div>
      <div class="snippet">${escapeHtml(r.snippet)}</div>
    </div>
  `).join("");
}

copyBtn.addEventListener("click", async () => {
  await navigator.clipboard.writeText(draftOutput.value);
  copyBtn.textContent = "कॉपी हो गया!";
  setTimeout(() => { copyBtn.textContent = "कॉपी करें"; }, 1500);
});

async function downloadExport(kind, button) {
  exportError.hidden = true;
  const originalText = button.textContent;
  button.disabled = true;
  button.textContent = "बन रहा है...";
  try {
    const resp = await fetch(`/api/export/${kind}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ draft: draftOutput.value }),
    });
    if (!resp.ok) {
      const body = await resp.json().catch(() => ({}));
      throw new Error(body.detail || `डाउनलोड विफल (HTTP ${resp.status})`);
    }
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = kind === "docx" ? "letter.docx" : "letter.pdf";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (err) {
    exportError.hidden = false;
    exportError.textContent = err.message;
  } finally {
    button.disabled = false;
    button.textContent = originalText;
  }
}

downloadDocxBtn.addEventListener("click", () => downloadExport("docx", downloadDocxBtn));
downloadPdfBtn.addEventListener("click", () => downloadExport("pdf", downloadPdfBtn));
