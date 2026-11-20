const STATUS_LABELS = {
  pending: "Đang chờ",
  processing: "Đang xử lý",
  completed: "Hoàn thành",
  failed: "Thất bại",
};
const STAGES = ["pending", "processing", "completed"];
const ordersBody = document.querySelector("#orders-body");
const createDialog = document.querySelector("#create-dialog");
const detailDialog = document.querySelector("#detail-dialog");
const itemList = document.querySelector("#item-list");
let orders = [];
let selectedOrder = null;
let notificationConnection = null;
let toastTimer;

const money = (amount) => new Intl.NumberFormat("vi-VN", { style: "currency", currency: "VND", maximumFractionDigits: 0 }).format(amount);
const dateTime = (value) => new Intl.DateTimeFormat("vi-VN", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
const dateOnly = (value) => new Intl.DateTimeFormat("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric" }).format(new Date(value));

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

async function request(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) {
    let message = "Không thể hoàn tất yêu cầu.";
    try { message = (await response.json()).detail || message; } catch {}
    throw new Error(message);
  }
  return response.json();
}

function showToast(message, isError = false) {
  const toast = document.querySelector("#toast");
  toast.textContent = message;
  toast.classList.toggle("error", isError);
  toast.classList.add("visible");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("visible"), 3000);
}

function renderOrders() {
  ordersBody.replaceChildren();
  for (const order of orders) {
    const row = node("tr");
    const idCell = node("td");
    const openButton = node("button", "order-link", order.id);
    openButton.type = "button";
    openButton.addEventListener("click", () => openDetails(order.id));
    idCell.append(openButton);

    const customerCell = node("td", "customer-cell");
    customerCell.append(node("strong", "", order.customer_name), node("small", "", order.customer_email));
    const dateCell = node("td", "", dateOnly(order.created_at));
    const totalCell = node("td", "", money(order.total));
    const statusCell = node("td");
    statusCell.append(node("span", `status-pill status-${order.status}`, STATUS_LABELS[order.status] || order.status));
    row.append(idCell, customerCell, dateCell, totalCell, statusCell);
    ordersBody.append(row);
  }
  document.querySelector("#empty-state").hidden = orders.length > 0;
  document.querySelector("#result-count").textContent = `${orders.length} đơn hàng`;
  document.querySelector("#last-updated").textContent = `Cập nhật ${new Intl.DateTimeFormat("vi-VN", { timeStyle: "short" }).format(new Date())}`;
}

async function loadOrders() {
  try {
    orders = await request("/orders");
    renderOrders();
  } catch (error) {
    document.querySelector("#result-count").textContent = "Không thể tải dữ liệu đơn hàng";
    showToast(error.message, true);
  }
}

function appendTimeline(order) {
  const list = document.querySelector("#detail-timeline");
  list.replaceChildren();
  const terminalFailure = order.status === "failed";
  const activeStage = terminalFailure ? -1 : STAGES.indexOf(order.status);
  for (const [index, stage] of STAGES.entries()) {
    const entry = node("li");
    if (index < activeStage) entry.classList.add("done");
    if (index === activeStage) entry.classList.add("current");
    const marker = node("span", "timeline-marker");
    marker.setAttribute("aria-hidden", "true");
    const copy = node("div", "timeline-copy");
    copy.append(node("strong", "", STATUS_LABELS[stage]));
    const update = order.timeline.find((item) => item.status === stage);
    if (update) {
      const time = node("time", "", dateTime(update.at));
      copy.append(time);
    }
    entry.append(marker, copy);
    list.append(entry);
  }
  if (terminalFailure) {
    const failed = node("li", "current");
    failed.append(node("span", "timeline-marker"));
    const copy = node("div", "timeline-copy");
    copy.append(node("strong", "", STATUS_LABELS.failed));
    const update = order.timeline.find((item) => item.status === "failed");
    if (update) copy.append(node("time", "", dateTime(update.at)));
    failed.append(copy);
    list.append(failed);
  }
}

function renderDetails(order) {
  selectedOrder = order;
  document.querySelector("#detail-title").textContent = order.id;
  const status = document.querySelector("#detail-status");
  status.replaceChildren(node("span", `status-pill status-${order.status}`, STATUS_LABELS[order.status] || order.status));
  document.querySelector("#detail-customer").textContent = order.customer_name;
  document.querySelector("#detail-email").textContent = order.customer_email;
  document.querySelector("#detail-total").textContent = money(order.total);
  document.querySelector("#detail-created").textContent = dateTime(order.created_at);
  const items = document.querySelector("#detail-items");
  items.replaceChildren();
  for (const item of order.items) {
    const row = node("div", "detail-item");
    row.append(node("span", "", `${item.name} × ${item.quantity}`), node("strong", "", money(item.unit_price * item.quantity)));
    items.append(row);
  }
  appendTimeline(order);
}

async function openDetails(orderId) {
  try {
    const order = await request(`/orders/${encodeURIComponent(orderId)}`);
    renderDetails(order);
    if (!detailDialog.open) detailDialog.showModal();
  } catch (error) {
    showToast(error.message, true);
  }
}

async function connectNotifications() {
  const indicator = document.querySelector("#stream-status");
  notificationConnection = new signalR.HubConnectionBuilder()
    .withUrl(`${window.location.protocol}//${window.location.hostname}:8001/notifications`)
    .withAutomaticReconnect()
    .build();
  notificationConnection.on("OrderUpdated", (updated) => {
    const previous = orders.find((order) => order.id === updated.id);
    orders = previous
      ? orders.map((order) => order.id === updated.id ? updated : order)
      : [updated, ...orders];
    renderOrders();
    if (selectedOrder?.id === updated.id) {
      const previousStatus = selectedOrder.status;
      renderDetails(updated);
      if (previousStatus !== updated.status) showToast(`${updated.id}: ${STATUS_LABELS[updated.status] || updated.status}`);
    }
  });
  notificationConnection.onreconnecting(() => indicator.classList.add("disconnected"));
  notificationConnection.onreconnected(() => indicator.classList.remove("disconnected"));
  notificationConnection.onclose(() => indicator.classList.add("disconnected"));
  try {
    await notificationConnection.start();
    indicator.classList.remove("disconnected");
  } catch {
    indicator.classList.add("disconnected");
    setTimeout(connectNotifications, 3000);
  }
}

function addItemRow(initial = {}) {
  const row = node("div", "item-row");
  const name = node("input");
  name.name = "item_name";
  name.required = true;
  name.maxLength = 100;
  name.placeholder = "Tên sản phẩm";
  name.value = initial.name || "";
  name.setAttribute("aria-label", "Tên sản phẩm");
  const quantity = node("input");
  quantity.name = "item_quantity";
  quantity.type = "number";
  quantity.min = "1";
  quantity.max = "999";
  quantity.step = "1";
  quantity.required = true;
  quantity.value = initial.quantity || 1;
  quantity.setAttribute("aria-label", "Số lượng");
  const price = node("input");
  price.name = "item_price";
  price.type = "number";
  price.min = "0";
  price.max = "1000000000";
  price.step = "1000";
  price.required = true;
  price.value = initial.unit_price || "";
  price.placeholder = "0";
  price.setAttribute("aria-label", "Đơn giá (VND)");
  const remove = node("button", "remove-item", "×");
  remove.type = "button";
  remove.setAttribute("aria-label", "Xóa sản phẩm");
  remove.addEventListener("click", () => {
    if (itemList.children.length === 1) return showToast("Đơn hàng cần ít nhất một sản phẩm.", true);
    row.remove();
    updateFormTotal();
  });
  row.append(name, quantity, price, remove);
  row.addEventListener("input", updateFormTotal);
  itemList.append(row);
}

function updateFormTotal() {
  const total = [...itemList.querySelectorAll(".item-row")].reduce((sum, row) => {
    const quantity = Number(row.querySelector('[name="item_quantity"]').value) || 0;
    const price = Number(row.querySelector('[name="item_price"]').value) || 0;
    return sum + quantity * price;
  }, 0);
  document.querySelector("#form-total").textContent = money(total);
}

document.querySelector("#open-create").addEventListener("click", () => createDialog.showModal());
document.querySelectorAll(".close-dialog").forEach((button) => button.addEventListener("click", () => createDialog.close()));
document.querySelector("#add-item").addEventListener("click", () => {
  if (itemList.children.length >= 20) return showToast("Mỗi đơn hàng tối đa 20 sản phẩm.", true);
  addItemRow();
});
document.querySelector("#refresh-orders").addEventListener("click", loadOrders);
document.querySelector(".close-detail").addEventListener("click", () => detailDialog.close());
detailDialog.addEventListener("click", (event) => { if (event.target === detailDialog) detailDialog.close(); });
createDialog.addEventListener("click", (event) => { if (event.target === createDialog) createDialog.close(); });

document.querySelector("#create-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const data = new FormData(form);
  const rows = [...itemList.querySelectorAll(".item-row")];
  const payload = {
    customer_name: data.get("customer_name").trim(),
    customer_email: data.get("customer_email").trim(),
    items: rows.map((row) => ({
      name: row.querySelector('[name="item_name"]').value.trim(),
      quantity: Number(row.querySelector('[name="item_quantity"]').value),
      unit_price: Number(row.querySelector('[name="item_price"]').value),
    })),
  };
  const submit = form.querySelector('[type="submit"]');
  submit.disabled = true;
  try {
    const order = await request("/orders", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    form.reset();
    itemList.replaceChildren();
    addItemRow();
    updateFormTotal();
    createDialog.close();
    await loadOrders();
    showToast(`Đơn ${order.id} đã vào hàng đợi.`);
    await openDetails(order.id);
  } catch (error) {
    showToast(error.message, true);
  } finally {
    submit.disabled = false;
  }
});

addItemRow();
updateFormTotal();
loadOrders();
connectNotifications();