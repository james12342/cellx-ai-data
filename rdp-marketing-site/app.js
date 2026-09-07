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
const authStatus = document.querySelector("[data-auth-status]");
const logoutButton = document.querySelector("[data-auth-logout]");
const loginButton = document.querySelector('[data-open-auth="login"]');
const registerButton = document.querySelector('[data-open-auth="register"]');

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

function readAccount() {
  try {
    return JSON.parse(localStorage.getItem("cell-ai-data-marketplace-user") || localStorage.getItem("cell-ai-data-demo-account") || "null");
  } catch {
    return null;
  }
}

function renderAuthState() {
  const account = readAccount();
  const signedIn = Boolean(account?.email);
  if (authStatus) {
    authStatus.hidden = !signedIn;
    authStatus.textContent = signedIn ? `Signed in: ${account.email}` : "";
  }
  if (logoutButton) logoutButton.hidden = !signedIn;
  if (loginButton) loginButton.hidden = signedIn;
  if (registerButton) registerButton.hidden = signedIn;
}

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
  document.querySelector("[data-auth-name]").closest("label").style.display = authMode === "register" ? "grid" : "none";
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
document.querySelector("[data-auth-form]").addEventListener("submit", async event => {
  event.preventDefault();
  const name = document.querySelector("[data-auth-name]").value || "";
  const email = document.querySelector("[data-auth-email]").value || "demo@company.com";
  const password = document.querySelector("[data-auth-password]").value || "";
  const role = document.querySelector("[data-auth-role]").value || "developer_member";
  try {
    const response = await fetch("https://app.cellaidata.com/ext-api/marketplace/" + authMode, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, email, password, role }),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.message || "Account request failed.");
    localStorage.setItem("cell-ai-data-marketplace-user", JSON.stringify(data.user));
    if (data.sessionToken) localStorage.setItem("cell-ai-data-marketplace-token", data.sessionToken);
    closeAuth();
    renderAuthState();
    showToast(`${data.user.email} ${authMode === "register" ? "registered" : "logged in"}: marketplace access enabled.`);
  } catch (error) {
    localStorage.setItem("cell-ai-data-demo-account", JSON.stringify({ name, email, role, mode: authMode, signedInAt: new Date().toISOString() }));
    closeAuth();
    renderAuthState();
    showToast(`Account saved locally for demo. Backend note: ${error.message}`);
  }
});

logoutButton?.addEventListener("click", () => {
  localStorage.removeItem("cell-ai-data-marketplace-user");
  localStorage.removeItem("cell-ai-data-marketplace-token");
  localStorage.removeItem("cell-ai-data-demo-account");
  renderAuthState();
  showToast("Logged out.");
});

document.querySelector("[data-contact-form]")?.addEventListener("submit", async event => {
  event.preventDefault();
  const payload = {
    email: document.querySelector("[data-contact-email]").value.trim(),
    phone: document.querySelector("[data-contact-phone]").value.trim(),
    message: document.querySelector("[data-contact-message]").value.trim(),
    source: "cellaidata.com contact form",
    createdAt: new Date().toISOString(),
  };
  try {
    const response = await fetch("https://app.cellaidata.com/ext-api/contact", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || data.ok === false) throw new Error(data.message || "Contact API is not ready yet.");
    event.target.reset();
    showToast("Contact request sent. We will follow up soon.");
  } catch (error) {
    const saved = JSON.parse(localStorage.getItem("cell-ai-data-contact-requests") || "[]");
    saved.unshift(payload);
    localStorage.setItem("cell-ai-data-contact-requests", JSON.stringify(saved.slice(0, 20)));
    event.target.reset();
    showToast(`Contact request saved for demo. Backend note: ${error.message}`);
  }
});

document.querySelector("[data-nav-toggle]").addEventListener("click", () => {
  document.querySelector("[data-nav]").classList.toggle("open");
});

document.querySelectorAll(".site-nav a").forEach(link => {
  link.addEventListener("click", () => document.querySelector("[data-nav]").classList.remove("open"));
});

updatePrices();
renderAuthState();
