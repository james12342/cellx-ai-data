const state = {
  billing: "monthly",
  plan: "Growth",
  price: "299",
  payment: "Stripe"
};

const prices = Array.from(document.querySelectorAll(".price-card"));
const summaryPlan = document.querySelector("[data-summary-plan]");
const summaryPrice = document.querySelector("[data-summary-price]");
const toast = document.querySelector("[data-toast]");

function showToast(message) {
  toast.textContent = message;
  toast.hidden = false;
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => {
    toast.hidden = true;
  }, 2800);
}

function updatePrices() {
  prices.forEach(card => {
    const amount = card.dataset[state.billing];
    card.querySelector("[data-price]").textContent = amount;
    if (card.dataset.plan === state.plan) {
      state.price = amount;
    }
  });
  summaryPlan.textContent = state.plan;
  summaryPrice.textContent = state.price;
}

document.querySelectorAll("[data-billing]").forEach(button => {
  button.addEventListener("click", () => {
    state.billing = button.dataset.billing;
    document.querySelectorAll("[data-billing]").forEach(item => item.classList.toggle("active", item === button));
    updatePrices();
  });
});

document.querySelectorAll("[data-select-plan]").forEach(button => {
  button.addEventListener("click", () => {
    const card = button.closest(".price-card");
    state.plan = card.dataset.plan;
    state.price = card.dataset[state.billing];
    updatePrices();
    document.querySelector("#checkout").scrollIntoView({ behavior: "smooth" });
  });
});

document.querySelectorAll("[data-payment]").forEach(button => {
  button.addEventListener("click", () => {
    state.payment = button.dataset.payment;
    document.querySelectorAll("[data-payment]").forEach(item => item.classList.toggle("active", item === button));
    const cardFields = document.querySelector("[data-card-fields]");
    cardFields.style.display = state.payment === "PayPal" ? "none" : "block";
  });
});

document.querySelector("[data-checkout-form]").addEventListener("submit", event => {
  event.preventDefault();
  showToast(`${state.plan} checkout selected with ${state.payment}. Connect this button to your payment backend on Lightsail.`);
});

const modal = document.querySelector("[data-demo-modal]");
function openDemo() {
  modal.hidden = false;
  document.body.classList.add("modal-open");
}
function closeDemo() {
  modal.hidden = true;
  document.body.classList.remove("modal-open");
}
document.querySelectorAll("[data-open-demo]").forEach(button => button.addEventListener("click", openDemo));
document.querySelector("[data-close-demo]").addEventListener("click", closeDemo);
modal.addEventListener("click", event => {
  if (event.target === modal) closeDemo();
});
document.querySelector("[data-demo-form]").addEventListener("submit", event => {
  event.preventDefault();
  closeDemo();
  showToast("Demo request captured. Connect this form to email, CRM, or an API endpoint.");
});

document.querySelector("[data-nav-toggle]").addEventListener("click", () => {
  document.querySelector("[data-nav]").classList.toggle("open");
});

document.querySelectorAll(".site-nav a").forEach(link => {
  link.addEventListener("click", () => document.querySelector("[data-nav]").classList.remove("open"));
});

updatePrices();
