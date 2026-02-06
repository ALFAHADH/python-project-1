const API_BASE = "/api";
const runtimeLog = document.getElementById("runtime-log");
const profileOutput = document.getElementById("profile-output");
const ordersList = document.getElementById("orders-list");

function log(message, payload = null) {
  const now = new Date().toISOString();
  const line = payload ? `${now} ${message} ${JSON.stringify(payload, null, 2)}` : `${now} ${message}`;
  runtimeLog.textContent = `${line}\n${runtimeLog.textContent}`;
}

function getToken() {
  return localStorage.getItem("access_token");
}

function setToken(token) {
  localStorage.setItem("access_token", token);
}

async function apiRequest(path, options = {}) {
  const token = getToken();
  const headers = {
    ...(options.headers || {}),
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const errorPayload = await response.json().catch(() => ({}));
    throw new Error(errorPayload.detail || `Request failed: ${response.status}`);
  }

  if (response.status === 204) {
    return null;
  }
  return response.json();
}

async function loadOrders() {
  try {
    const orders = await apiRequest("/orders/");
    ordersList.innerHTML = "";

    orders.forEach((order) => {
      const item = document.createElement("li");
      item.className = "order-item";
      item.innerHTML = `
        <div>
          <strong>#${order.id} ${order.title}</strong>
          <span>Status: ${order.status}</span>
          <span>Amount: $${order.total_amount}</span>
          <span>Priority: ${order.priority}</span>
          <p>${order.description || ""}</p>
        </div>
        <div class="row-actions">
          <button data-action="complete" data-id="${order.id}">Mark Completed</button>
          <button data-action="cancel" data-id="${order.id}">Cancel</button>
          <button data-action="delete" data-id="${order.id}">Delete</button>
        </div>
      `;
      ordersList.appendChild(item);
    });

    log("Loaded orders", { count: orders.length });
  } catch (error) {
    log("Failed to load orders", { error: error.message });
  }
}

async function updateOrderStatus(orderId, status) {
  try {
    await apiRequest(`/orders/${orderId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    });
    log("Order updated", { orderId, status });
    await loadOrders();
  } catch (error) {
    log("Failed to update order", { error: error.message, orderId, status });
  }
}

async function deleteOrder(orderId) {
  try {
    await apiRequest(`/orders/${orderId}`, { method: "DELETE" });
    log("Order deleted", { orderId });
    await loadOrders();
  } catch (error) {
    log("Failed to delete order", { error: error.message, orderId });
  }
}

document.getElementById("register-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = {
    full_name: document.getElementById("register-name").value,
    email: document.getElementById("register-email").value,
    password: document.getElementById("register-password").value,
  };

  try {
    const user = await apiRequest("/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    log("User registered", user);
  } catch (error) {
    log("Registration failed", { error: error.message });
  }
});

document.getElementById("login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const email = document.getElementById("login-email").value;
  const password = document.getElementById("login-password").value;

  const form = new URLSearchParams();
  form.append("username", email);
  form.append("password", password);

  try {
    const tokenResponse = await apiRequest("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form.toString(),
    });
    setToken(tokenResponse.access_token);
    log("Login successful");
    await loadOrders();
  } catch (error) {
    log("Login failed", { error: error.message });
  }
});

document.getElementById("order-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = {
    title: document.getElementById("order-title").value,
    description: document.getElementById("order-description").value,
    total_amount: Number(document.getElementById("order-amount").value),
    priority: Number(document.getElementById("order-priority").value),
  };

  try {
    const order = await apiRequest("/orders/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    log("Order created", order);
    await loadOrders();
  } catch (error) {
    log("Failed to create order", { error: error.message });
  }
});

document.getElementById("refresh-orders").addEventListener("click", async () => {
  await loadOrders();
});

document.getElementById("load-profile").addEventListener("click", async () => {
  try {
    const profile = await apiRequest("/users/me");
    profileOutput.textContent = JSON.stringify(profile, null, 2);
    log("Loaded profile", profile);
  } catch (error) {
    log("Failed to load profile", { error: error.message });
  }
});

ordersList.addEventListener("click", async (event) => {
  const target = event.target;
  if (!(target instanceof HTMLButtonElement)) return;

  const id = Number(target.dataset.id);
  const action = target.dataset.action;

  if (!id || !action) return;

  if (action === "complete") {
    await updateOrderStatus(id, "completed");
  } else if (action === "cancel") {
    await updateOrderStatus(id, "canceled");
  } else if (action === "delete") {
    await deleteOrder(id);
  }
});

log("Frontend initialized. Login to start using the API.");

