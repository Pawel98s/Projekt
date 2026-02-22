async function deleteProduct(id) {
  if (!confirm("Czy na pewno chcesz usunąć produkt?")) return;
  const params = new URLSearchParams(window.location.search);
  const res = await fetch(`/delete/${id}?${params}`, { method: "DELETE" });
  if (res.ok) location.reload();
}

async function deleteReview(id) {
  if (!confirm("Usunąć opinię?")) return;
  const res = await fetch(`/delete_review/${id}`, { method: "DELETE" });
  if (res.ok) location.reload();
}

function startEditReview(button, reviewId) {
  const reviewItem = button.closest(".review-item");
  const textDiv = reviewItem.querySelector(".review-text");

  if (reviewItem.classList.contains("editing")) return;
  reviewItem.classList.add("editing");

  const originalText = textDiv.innerText.replace(/^“|”$/g, "");

  textDiv.innerHTML = `
      <textarea class="form-control mb-2" rows="2">${originalText}</textarea>
      <div>
          <button class="btn btn-sm btn-success me-1">💾 Zapisz</button>
          <button class="btn btn-sm btn-secondary">✖ Anuluj</button>
      </div>
  `;

  const textarea = textDiv.querySelector("textarea");
  const saveBtn = textDiv.querySelector(".btn-success");
  const cancelBtn = textDiv.querySelector(".btn-secondary");

  saveBtn.onclick = async () => {
    const newText = textarea.value.trim();
    if (!newText) return;

    const res = await fetch(`/edit_review/${reviewId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ review_text: newText })
    });

    if (res.ok) {
      textDiv.innerHTML = `“${newText}”`;
      reviewItem.classList.remove("editing");
    }
  };

  cancelBtn.onclick = () => {
    textDiv.innerHTML = `“${originalText}”`;
    reviewItem.classList.remove("editing");
  };
}

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".md").forEach(el => {
    el.innerHTML = marked.parse(el.innerText);
  });

  document.querySelectorAll(".add-review-form").forEach(form => {
    form.addEventListener("submit", async e => {
      e.preventDefault();
      const productId = form.dataset.productId;
      const text = form.querySelector("textarea").value.trim();
      if (!text) return;

      const res = await fetch("/addReview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ product_id: productId, review_text: text })
      });

      if (res.ok) location.reload();
    });
  });

  const perPageSelect = document.getElementById("perPageSelect");
  if (perPageSelect) {
    perPageSelect.addEventListener("change", function () {
      document.getElementById("searchForm").submit();
    });
  }
});