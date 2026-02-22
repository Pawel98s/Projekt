function sortTable(col) {
  let table = document.getElementById("logTable");
  let rows = Array.from(table.rows).slice(1);
  let asc = table.getAttribute("data-sort") !== "asc";

  rows.sort((a, b) => {
    let A = a.cells[col].innerText.trim();
    let B = b.cells[col].innerText.trim();
    return asc ? A.localeCompare(B) : B.localeCompare(A);
  });

  rows.forEach(r => table.appendChild(r));
  table.setAttribute("data-sort", asc ? "asc" : "desc");
}

function filterLogs() {
  let filter = document.getElementById("search").value.toLowerCase();
  let rows = document.querySelectorAll("#logTable tr");

  rows.forEach((row, idx) => {
    if (idx === 0) return;
    let text = row.innerText.toLowerCase();
    row.style.display = text.includes(filter) ? "" : "none";
  });
}