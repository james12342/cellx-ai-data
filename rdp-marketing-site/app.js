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
const authModal = document.querySelector("[data-auth-modal]");
let authMode = "login";

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

function setAuthMode(mode) {
  authMode = mode === "register" ? "register" : "login";
  document.querySelectorAll("[data-auth-tab]").forEach(button => {
    button.classList.toggle("active", button.dataset.authTab === authMode);
  });
  document.getElementById("authTitle").textContent = authMode === "register" ? "Create developer marketplace account" : "Login to Cell AI Data";
}

function openAuth(mode = "login") {
  setAuthMode(mode);
  authModal.hidden = false;
  document.body.classList.add("modal-open");
}

function closeAuth() {
  authModal.hidden = true;
  document.body.classList.remove("modal-open");
}

document.querySelectorAll("[data-open-auth]").forEach(button => {
  button.addEventListener("click", () => openAuth(button.dataset.openAuth));
});
document.querySelectorAll("[data-auth-tab]").forEach(button => {
  button.addEventListener("click", () => setAuthMode(button.dataset.authTab));
});
document.querySelector("[data-close-auth]").addEventListener("click", closeAuth);
authModal.addEventListener("click", event => {
  if (event.target === authModal) closeAuth();
});
document.querySelector("[data-auth-form]").addEventListener("submit", event => {
  event.preventDefault();
  const email = document.querySelector("[data-auth-email]").value || "demo@company.com";
  const role = document.querySelector("[data-auth-role]").value || "Developer member";
  localStorage.setItem("cell-ai-data-demo-account", JSON.stringify({ email, role, mode: authMode, signedInAt: new Date().toISOString() }));
  closeAuth();
  showToast(`${role} ${authMode === "register" ? "registered" : "logged in"}: marketplace access enabled.`);
});

document.querySelector("[data-nav-toggle]").addEventListener("click", () => {
  document.querySelector("[data-nav]").classList.toggle("open");
});

document.querySelectorAll(".site-nav a").forEach(link => {
  link.addEventListener("click", () => document.querySelector("[data-nav]").classList.remove("open"));
});

updatePrices();
