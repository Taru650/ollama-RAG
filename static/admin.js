function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s == null ? "" : String(s);
  return div.innerHTML;
}

const documentsTbody = document.getElementById("documents-tbody");
const deptList = document.getElementById("dept-list");

async function loadDepartmentsList() {
  const departments = await fetch("/api/departments").then(r => r.json()).catch(() => []);
  deptList.innerHTML = departments.map(d => `<option value="${escapeHtml(d)}">`).join("");
}

async function loadDocuments() {
  documentsTbody.innerHTML = `<tr><td colspan="5">लोड हो रहा है...</td></tr>`;
  const docs = await fetch("/api/admin/documents").then(r => r.json());
  if (!docs.length) {
    documentsTbody.innerHTML = `<tr><td colspan="5">कोई दस्तावेज़ नहीं मिला। ऊपर अपलोड करें।</td></tr>`;
    return;
  }
  documentsTbody.innerHTML = docs.map(d => `
    <tr>
      <td>${escapeHtml(d.source_file.split("/").pop())}</td>
      <td>${escapeHtml(d.department)} / ${escapeHtml(d.office)}</td>
      <td>${d.segment_count}</td>
      <td>${d.needs_review_count > 0
          ? `<span class="pill review">${d.needs_review_count}</span>`
          : `<span class="pill ok">0</span>`}</td>
      <td>
        <button data-action="view" data-doc-id="${d.doc_id}">देखें</button>
        <button data-action="delete" data-doc-id="${d.doc_id}" class="btn-danger">हटाएँ</button>
      </td>
    </tr>
    <tr class="detail-row" id="detail-${d.doc_id}" hidden>
      <td colspan="5"></td>
    </tr>
  `).join("");
  loadDepartmentsList();
}

documentsTbody.addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-action]");
  if (!btn) return;
  const docId = btn.dataset.docId;

  if (btn.dataset.action === "delete") {
    if (!confirm("क्या आप वाकई इस दस्तावेज़ को हटाना चाहते हैं? यह क्रिया पूर्ववत नहीं की जा सकती।")) return;
    const resp = await fetch(`/api/admin/documents/${docId}`, { method: "DELETE" });
    if (resp.ok) {
      loadDocuments();
    } else {
      const body = await resp.json().catch(() => ({}));
      alert("हटाने में विफल: " + (body.detail || resp.status));
    }
    return;
  }

  if (btn.dataset.action === "view") {
    const detailRow = document.getElementById(`detail-${docId}`);
    if (!detailRow.hidden) { detailRow.hidden = true; return; }
    detailRow.hidden = false;
    detailRow.querySelector("td").innerHTML = "लोड हो रहा है...";
    const segments = await fetch(`/api/admin/documents/${docId}`).then(r => r.json());
    detailRow.querySelector("td").innerHTML = segments.map(renderSegment).join("");
  }
});

function renderSegment(seg) {
  return `
    <div style="border:1px solid var(--border); border-radius:6px; padding:10px; margin:8px 0;">
      <div style="font-size:12px; color:var(--muted); margin-bottom:6px;">
        ${escapeHtml(seg.letter_id)}
        ${seg.needs_review ? `<span class="pill review">समीक्षा आवश्यक</span>` : ""}
      </div>
      <details>
        <summary>पाठ देखें</summary>
        <pre style="white-space:pre-wrap; font-size:13px; max-height:200px; overflow:auto;">${escapeHtml(seg.text)}</pre>
      </details>
      <form class="inline meta-edit-form" data-letter-id="${seg.letter_id}" style="margin-top:8px;">
        <div>
          <label>विभाग</label>
          <input type="text" name="department" value="${escapeHtml(seg.department)}">
        </div>
        <div>
          <label>पत्र प्रकार</label>
          <input type="text" name="letter_type" value="${escapeHtml(seg.letter_type || "")}">
        </div>
        <div>
          <label>विषय</label>
          <input type="text" name="subject" value="${escapeHtml(seg.subject || "")}">
        </div>
        <div style="flex:0 0 auto;">
          <button type="submit">सहेजें</button>
        </div>
      </form>
    </div>
  `;
}

documentsTbody.addEventListener("submit", async (e) => {
  const form = e.target.closest(".meta-edit-form");
  if (!form) return;
  e.preventDefault();
  const letterId = form.dataset.letterId;
  const payload = {};
  for (const field of ["department", "letter_type", "subject"]) {
    const value = form.elements[field].value.trim();
    if (value) payload[field] = value;
  }
  const resp = await fetch(`/api/admin/letters/${letterId}/metadata`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (resp.ok) {
    loadDocuments();
  } else {
    const body = await resp.json().catch(() => ({}));
    alert("सहेजने में विफल: " + (body.detail || resp.status));
  }
});

document.getElementById("upload-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const uploadError = document.getElementById("upload-error");
  const uploadSuccess = document.getElementById("upload-success");
  const uploadBtn = document.getElementById("upload-btn");
  uploadError.hidden = true;
  uploadSuccess.hidden = true;

  const fileInput = document.getElementById("upload-file");
  const file = fileInput.files[0];
  if (!file) return;

  const formData = new FormData();
  formData.append("file", file);
  formData.append("department", document.getElementById("upload-department").value.trim());
  formData.append("office", document.getElementById("upload-office").value.trim());

  uploadBtn.disabled = true;
  uploadBtn.textContent = "अपलोड हो रहा है...";
  try {
    const resp = await fetch("/api/admin/upload", { method: "POST", body: formData });
    const body = await resp.json();
    if (!resp.ok) throw new Error(body.detail || `HTTP ${resp.status}`);
    uploadSuccess.hidden = false;
    uploadSuccess.textContent =
      `${body.letters_found} पत्र मिले, ${body.letters_indexed} इंडेक्स किए गए` +
      (body.needs_review > 0 ? `, ${body.needs_review} को समीक्षा की आवश्यकता है।` : "।");
    fileInput.value = "";
    loadDocuments();
  } catch (err) {
    uploadError.hidden = false;
    uploadError.textContent = err.message;
  } finally {
    uploadBtn.disabled = false;
    uploadBtn.textContent = "अपलोड करें";
  }
});

document.getElementById("reindex-btn").addEventListener("click", async () => {
  const status = document.getElementById("reindex-status");
  status.hidden = false;
  status.textContent = "पूरा इंडेक्स फिर से बन रहा है...";
  try {
    const resp = await fetch("/api/admin/reindex", { method: "POST" });
    const body = await resp.json();
    if (!resp.ok) throw new Error(body.detail || `HTTP ${resp.status}`);
    status.textContent = `पूर्ण: ${body.letters_found} पत्र मिले, ${body.letters_indexed} इंडेक्स किए गए, ${body.needs_review} को समीक्षा चाहिए।`;
    loadDocuments();
  } catch (err) {
    status.textContent = "विफल: " + err.message;
  }
});

document.getElementById("search-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const q = document.getElementById("search-query").value.trim();
  const resultsDiv = document.getElementById("search-results");
  if (!q) { resultsDiv.innerHTML = ""; return; }
  resultsDiv.innerHTML = "खोज रहे हैं...";
  const results = await fetch(`/api/admin/search?q=${encodeURIComponent(q)}`).then(r => r.json());
  if (!results.length) {
    resultsDiv.innerHTML = "<p>कोई परिणाम नहीं मिला।</p>";
    return;
  }
  resultsDiv.innerHTML = `
    <table><thead><tr><th>पत्र</th><th>विभाग</th><th>विषय</th></tr></thead><tbody>
    ${results.map(r => `
      <tr>
        <td>${escapeHtml(r.letter_id)}</td>
        <td>${escapeHtml(r.department)}</td>
        <td>${escapeHtml(r.subject || "")}</td>
      </tr>
    `).join("")}
    </tbody></table>
  `;
});

loadDocuments();
