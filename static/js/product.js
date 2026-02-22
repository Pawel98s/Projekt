document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".md").forEach(el => {
    el.innerHTML = marked.parse(el.innerText);
  });

  const form = document.getElementById("addReviewForm");
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const textarea = form.querySelector("textarea");
    const text = (textarea?.value || "").trim();
    if (!text) return;

    const productId = form.dataset.productId;
    if (!productId) {
      console.error("Brak data-product-id na #addReviewForm");
      return;
    }

    const res = await fetch("/addReview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        product_id: Number(productId),
        review_text: text
      })
    });

    if (res.ok) location.reload();
  });
});

async function deleteReview(id) {
  if (!confirm("Usunąć opinię?")) return;
  const res = await fetch(`/delete_review/${id}`, { method: "DELETE" });
  if (res.ok) location.reload();
}

function startEditReview(btn, id) {
  const item = btn.closest(".review-item");
  if (!item || item.classList.contains("editing")) return;

  item.classList.add("editing");
  const textDiv = item.querySelector(".review-text");
  if (!textDiv) return;

  const original = textDiv.innerText.replace(/^“|”$/g, "");

  textDiv.innerHTML = `
    <textarea class="form-control mb-2">${original}</textarea>
    <button class="btn btn-sm btn-success me-1">💾</button>
    <button class="btn btn-sm btn-secondary">✖</button>
  `;

  const buttons = textDiv.querySelectorAll("button");
  const save = buttons[0];
  const cancel = buttons[1];

  save.onclick = async () => {
    const text = textDiv.querySelector("textarea").value.trim();
    if (!text) return;

    const res = await fetch(`/edit_review/${id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ review_text: text })
    });

    if (res.ok) location.reload();
  };

  cancel.onclick = () => location.reload();
}