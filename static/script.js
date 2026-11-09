const $ = (selector) => document.querySelector(selector);

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[char]));
}

async function api(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || "Request failed. Please try again.");
  return data;
}

function showMessage(selector, message, isError = false) {
  const element = $(selector);
  element.textContent = message;
  element.className = `form-message ${isError ? "error" : "success"}`;
}

async function loadHealth() {
  const badge = $("#connectionStatus");
  try {
    await api("/api/health");
    badge.textContent = "MySQL connected";
    badge.style.background = "rgba(21, 115, 71, .25)";
  } catch (error) {
    badge.textContent = "Database connection failed — check setup";
    badge.style.background = "rgba(180, 35, 24, .25)";
  }
}

async function loadPapers(search = "") {
  const papers = await api(`/api/papers?search=${encodeURIComponent(search)}`);
  const tbody = $("#papersTable");
  if (!papers.length) {
    tbody.innerHTML = '<tr><td colspan="5">No papers found. Add the first paper using the form below.</td></tr>';
  } else {
    tbody.innerHTML = papers.map(p => `
      <tr>
        <td>${escapeHtml(p.title)}${p.doi ? `<small class="hint"><br>DOI: ${escapeHtml(p.doi)}</small>` : ""}</td>
        <td>${escapeHtml(p.authors || "Not assigned")}</td>
        <td>${escapeHtml(p.publication_year || "—")}</td>
        <td>${escapeHtml(p.journal_name || "—")}</td>
        <td>${Number(p.citation_count || 0)}</td>
      </tr>`).join("");
  }

  // Keep citation dropdowns in sync with the current paper list.
  const options = '<option value="">Choose a paper</option>' + papers.map(p =>
    `<option value="${p.paper_id}">${escapeHtml(p.title)} (ID ${p.paper_id})</option>`
  ).join("");
  $("#citingPaper").innerHTML = options;
  $("#citedPaper").innerHTML = options;
}

async function loadAuthors() {
  const authors = await api("/api/authors");
  const tbody = $("#authorsTable");
  if (!authors.length) {
    tbody.innerHTML = '<tr><td colspan="4">No authors yet.</td></tr>';
    return;
  }
  tbody.innerHTML = authors.map(a => `
    <tr>
      <td>${escapeHtml(a.author_name)}</td>
      <td>${escapeHtml(a.email || "—")}</td>
      <td>${escapeHtml(a.affiliation || "—")}</td>
      <td>${Number(a.publication_count || 0)}</td>
    </tr>`).join("");
}

async function loadStatistics() {
  const stats = await api("/api/statistics");
  $("#totalPapers").textContent = stats.total_papers;
  $("#totalAuthors").textContent = stats.total_authors;
  $("#totalCitations").textContent = stats.total_citations;
  const list = $("#topPapers");
  if (!stats.top_papers.length) {
    list.innerHTML = "<li>No papers recorded yet.</li>";
  } else {
    list.innerHTML = stats.top_papers.map(p =>
      `<li>${escapeHtml(p.title)}<small>${Number(p.citation_count)} citation(s)</small></li>`
    ).join("");
  }
}

async function refreshPage(search = "") {
  try {
    await Promise.all([loadPapers(search), loadAuthors(), loadStatistics()]);
  } catch (error) {
    console.error(error);
    showMessage("#paperMessage", error.message, true);
  }
}

$("#paperForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector('button[type="submit"]');
  const data = Object.fromEntries(new FormData(form).entries());
  button.disabled = true;
  try {
    const result = await api("/api/papers", {
      method: "POST",
      body: JSON.stringify(data)
    });
    showMessage("#paperMessage", `${result.message} Paper ID: ${result.paper_id}`);
    form.reset();
    form.elements.publication_year.value = new Date().getFullYear();
    await refreshPage($("#searchInput").value.trim());
  } catch (error) {
    showMessage("#paperMessage", error.message, true);
  } finally {
    button.disabled = false;
  }
});

$("#citationForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const data = Object.fromEntries(new FormData(form).entries());
  try {
    const result = await api("/api/citations", {
      method: "POST",
      body: JSON.stringify(data)
    });
    showMessage("#citationMessage", result.message);
    form.reset();
    await refreshPage($("#searchInput").value.trim());
  } catch (error) {
    showMessage("#citationMessage", error.message, true);
  }
});

let searchTimer;
$("#searchInput").addEventListener("input", (event) => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => loadPapers(event.target.value.trim()).catch(error => {
    $("#papersTable").innerHTML = `<tr><td colspan="5">${escapeHtml(error.message)}</td></tr>`;
  }), 250);
});

(async function init() {
  await loadHealth();
  await refreshPage();
})();
