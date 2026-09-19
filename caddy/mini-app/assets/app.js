"use strict";

const telegram = window.Telegram?.WebApp ?? null;
const CLIENT_INSTANCE_STORAGE_KEY = "workplayvpn.client-instance.v1";

let cachedClientInstanceId = null;

const state = {
  me: null,
  catalog: null,
  devices: [],
  payment: null,
  deleteDeviceId: null,
  toastTimer: null,
  telegramEventsBound: false,
  initialViewApplied: false,
};

const THEMES = {
  dark: {
    header: "#081321",
    background: "#07111e",
    bottomBar: "#081423",
  },
  light: {
    header: "#f7f9fc",
    background: "#edf3f9",
    bottomBar: "#ffffff",
  },
};

const elements = {
  loading: document.querySelector("#loading-screen"),
  error: document.querySelector("#error-screen"),
  errorMessage: document.querySelector("#error-message"),
  app: document.querySelector("#app"),
  retryButton: document.querySelector("#retry-button"),
  refreshButton: document.querySelector("#refresh-button"),
  firstName: document.querySelector("#user-first-name"),
  subscriptionCard: document.querySelector("#subscription-card"),
  subscriptionLabel: document.querySelector("#subscription-label"),
  subscriptionTitle: document.querySelector("#subscription-title"),
  subscriptionDescription: document.querySelector("#subscription-description"),
  subscriptionExpiry: document.querySelector("#subscription-expiry"),
  deviceSummary: document.querySelector("#device-summary"),
  pendingPayment: document.querySelector("#pending-payment"),
  pendingPaymentAmount: document.querySelector("#pending-payment-amount"),
  resumePaymentButton: document.querySelector("#resume-payment-button"),
  trialButton: document.querySelector("#trial-button"),
  plansList: document.querySelector("#plans-list"),
  plansStartingPrice: document.querySelector("#plans-starting-price"),
  plansDeviceLimit: document.querySelector("#plans-device-limit"),
  addDeviceButton: document.querySelector("#add-device-button"),
  deviceLimitAlert: document.querySelector("#device-limit-alert"),
  devicesList: document.querySelector("#devices-list"),
  devicesCounter: document.querySelector("#devices-counter"),
  changeRegionButton: document.querySelector("#change-region-button"),
  currentRegionName: document.querySelector("#current-region-name"),
  profileAvatar: document.querySelector("#profile-avatar"),
  profileName: document.querySelector("#profile-name"),
  profileUsername: document.querySelector("#profile-username"),
  profileTelegramId: document.querySelector("#profile-telegram-id"),
  profileSubscription: document.querySelector("#profile-subscription"),
  profileDevices: document.querySelector("#profile-devices"),
  locationSheet: document.querySelector("#location-sheet"),
  closeLocationSheet: document.querySelector("#close-location-sheet"),
  locationsList: document.querySelector("#locations-list"),
  deviceSetupSheet: document.querySelector("#device-setup-sheet"),
  closeDeviceSetup: document.querySelector("#close-device-setup"),
  detectedDeviceIcon: document.querySelector("#detected-device-icon"),
  detectedDeviceName: document.querySelector("#detected-device-name"),
  detectedDevicePlatform: document.querySelector("#detected-device-platform"),
  confirmDeviceSetup: document.querySelector("#confirm-device-setup"),
  regionSuccessSheet: document.querySelector("#region-success-sheet"),
  regionSuccessClose: document.querySelector("#region-success-close"),
  confirmSheet: document.querySelector("#confirm-sheet"),
  confirmMessage: document.querySelector("#confirm-message"),
  confirmCancel: document.querySelector("#confirm-cancel"),
  confirmDelete: document.querySelector("#confirm-delete"),
  toast: document.querySelector("#toast"),
};

class ApiError extends Error {
  constructor(status, detail) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

function haptic(type = "light") {
  try {
    telegram?.HapticFeedback?.impactOccurred(type);
  } catch {
    // Haptic feedback is optional.
  }
}

function applyTheme() {
  const theme = telegram?.colorScheme === "light" ? "light" : "dark";
  const colors = THEMES[theme];

  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme;

  try {
    telegram?.setHeaderColor(colors.header);
    telegram?.setBackgroundColor(colors.background);

    if (telegram?.isVersionAtLeast?.("7.10")) {
      telegram.setBottomBarColor(colors.bottomBar);
    }
  } catch {
    // Older Telegram clients can still use the CSS theme.
  }
}

function showToast(message, kind = "success") {
  window.clearTimeout(state.toastTimer);
  elements.toast.textContent = message;
  elements.toast.classList.toggle("error", kind === "error");
  elements.toast.classList.remove("hidden");

  state.toastTimer = window.setTimeout(() => {
    elements.toast.classList.add("hidden");
  }, 3400);
}

function humanError(error) {
  const detail = error instanceof ApiError ? error.detail : "";

  const translations = {
    "Trial already used": "Пробный период уже был использован.",
    "User already has active subscription": "У вас уже есть активная подписка.",
    "Active subscription required": "Сначала активируйте подписку.",
    "Subscription expired": "Срок подписки закончился.",
    "Device limit reached": "Достигнут лимит устройств.",
    "Device name already exists": "Такое устройство уже подключено. Обновите список и повторите.",
    "VPN node not found": "В выбранной стране пока нет доступного сервера.",
    "VPN node unavailable": "Сервер временно недоступен. Попробуйте позже.",
    "Location not found": "Выбранная страна больше недоступна.",
    "Plan not found": "Тариф больше недоступен.",
    "Paid plans require payment": "Для этого тарифа требуется оплата.",
    "User is inactive": "Аккаунт временно отключён.",
    "Invalid Telegram Mini App credentials": "Не удалось подтвердить вход через Telegram.",
    "Telegram Mini App credentials expired": "Сеанс устарел. Закройте и снова откройте приложение.",
  };

  if (translations[detail]) {
    return translations[detail];
  }

  if (error instanceof ApiError && error.status >= 500) {
    return "Сервис временно недоступен. Попробуйте немного позже.";
  }

  return "Не удалось выполнить действие. Попробуйте ещё раз.";
}

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set("X-Telegram-Init-Data", telegram.initData);

  if (options.body) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(path, {
    ...options,
    headers,
    credentials: "same-origin",
  });

  if (!response.ok) {
    let detail = "";

    try {
      const data = await response.json();
      detail = typeof data.detail === "string" ? data.detail : "";
    } catch {
      detail = "";
    }

    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) {
    return null;
  }

  return response.json();
}

function formatDate(value) {
  if (!value) {
    return "—";
  }

  const date = new Date(value);

  return new Intl.DateTimeFormat("ru-RU", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(date);
}

function formatMoney(amount, currency = "RUB") {
  const value = Number(amount);

  return new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(value);
}

function createIcon(pathMarkup) {
  const wrapper = document.createElement("span");
  wrapper.className = "device-icon";
  wrapper.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true">${pathMarkup}</svg>`;
  return wrapper;
}

function detectDevice() {
  const userAgent = navigator.userAgent || "";
  const platform = navigator.platform || "";

  if (/iPhone/i.test(userAgent)) {
    return { name: "iPhone", platform: "iOS", icon: "📱" };
  }

  if (
    /iPad/i.test(userAgent)
    || (/Macintosh/i.test(userAgent) && navigator.maxTouchPoints > 1)
  ) {
    return { name: "iPad", platform: "iPadOS", icon: "▣" };
  }

  if (/Android/i.test(userAgent)) {
    const modelMatch = userAgent.match(/Android[^;]*;\s*([^;)]+?)(?:\s+Build\/|;|\))/i);
    const model = modelMatch?.[1]?.trim();
    return {
      name: model && model.length <= 60 ? model : "Android",
      platform: "Android",
      icon: "🤖",
    };
  }

  if (/Windows/i.test(userAgent)) {
    return { name: "Windows PC", platform: "Windows", icon: "▦" };
  }

  if (/Macintosh|Mac OS X/i.test(userAgent)) {
    return { name: "Mac", platform: "macOS", icon: "◆" };
  }

  if (/Linux/i.test(platform)) {
    return { name: "Linux PC", platform: "Linux", icon: "🐧" };
  }

  return { name: "Устройство", platform: "Не определена", icon: "📱" };
}

function deviceDisplayName(device) {
  const baseName = device.platform === "Не определена"
    ? device.name
    : `${device.name} (${device.platform})`;

  const matchingDevices = state.devices.filter((existingDevice) =>
    existingDevice.device_name.toLowerCase().startsWith(device.name.toLowerCase())
  );

  if (matchingDevices.length === 0) {
    return baseName;
  }

  return device.platform === "Не определена"
    ? `${device.name} ${matchingDevices.length + 1}`
    : `${device.name} ${matchingDevices.length + 1} (${device.platform})`;
}

function setView(name) {
  document.querySelectorAll(".view").forEach((view) => {
    view.classList.toggle("active", view.id === `view-${name}`);
  });

  document.querySelectorAll(".nav-item").forEach((button) => {
    button.classList.toggle("active", button.dataset.viewLink === name);
  });

  if (telegram?.BackButton) {
    if (name === "home") {
      telegram.BackButton.hide();
    } else {
      telegram.BackButton.show();
    }
  }

  window.scrollTo({ top: 0, behavior: "smooth" });
  haptic("light");
}

function renderSubscription() {
  const { subscription, devices } = state.me;
  const isActive = subscription?.status === "active";

  elements.subscriptionCard.classList.toggle("is-active", isActive);
  elements.deviceSummary.textContent =
    `${devices.active_count} из ${devices.total_limit}`;

  if (isActive) {
    elements.subscriptionLabel.textContent = "Подписка активна";
    elements.subscriptionTitle.textContent = subscription.plan_name;
    elements.subscriptionDescription.textContent =
      "Защищённое подключение доступно на ваших устройствах.";
    elements.subscriptionExpiry.textContent =
      formatDate(subscription.expires_at);
  } else if (subscription?.status === "pending") {
    elements.subscriptionLabel.textContent = "Ожидает оплаты";
    elements.subscriptionTitle.textContent = subscription.plan_name;
    elements.subscriptionDescription.textContent =
      "Завершите оплату, чтобы активировать подключение.";
    elements.subscriptionExpiry.textContent = "после оплаты";
  } else {
    elements.subscriptionLabel.textContent = "Нет активной подписки";
    elements.subscriptionTitle.textContent = "Подключение неактивно";
    elements.subscriptionDescription.textContent =
      "Выберите тариф или воспользуйтесь пробным периодом.";
    elements.subscriptionExpiry.textContent = "—";
  }

  const canStartTrial = (
    state.me.trial_available
    && state.me.subscription?.status !== "active"
  );

  elements.trialButton.classList.toggle(
    "hidden",
    !canStartTrial
  );
}

function renderPayment() {
  const payment = state.payment;
  const resumable = Boolean(
    payment &&
    payment.status === "pending" &&
    payment.confirmation_url
  );

  elements.pendingPayment.classList.toggle("hidden", !resumable);

  if (resumable) {
    elements.pendingPaymentAmount.textContent =
      formatMoney(payment.amount, payment.currency);
  }
}

function renderProfile() {
  const user = state.me.user;
  const subscription = state.me.subscription;
  const initial = user.first_name.trim().charAt(0).toUpperCase() || "W";

  elements.firstName.textContent = user.first_name;
  elements.profileAvatar.textContent = initial;
  elements.profileName.textContent = user.first_name;
  elements.profileUsername.textContent =
    user.username ? `@${user.username}` : "Имя пользователя не указано";
  elements.profileTelegramId.textContent = String(user.telegram_id);
  elements.profileSubscription.textContent =
    subscription?.status === "active"
      ? subscription.plan_name
      : "Не активна";
  elements.profileDevices.textContent =
    `${state.me.devices.active_count} из ${state.me.devices.total_limit}`;
}

function renderPlans() {
  elements.plansList.replaceChildren();

  if (state.catalog.plans.length > 0) {
    const cheapestPlan = state.catalog.plans.reduce((cheapest, plan) => (
      Number(plan.price_amount) < Number(cheapest.price_amount)
        ? plan
        : cheapest
    ));
    const deviceLimit = Math.max(
      ...state.catalog.plans.map((plan) => plan.device_limit)
    );

    elements.plansStartingPrice.textContent =
      `От ${formatMoney(cheapestPlan.price_amount, cheapestPlan.currency)} `
      + `за ${cheapestPlan.name.toLowerCase()}`;
    elements.plansDeviceLimit.textContent =
      `В каждом тарифе доступно до ${deviceLimit} устройств.`;
  } else {
    elements.plansStartingPrice.textContent = "Тарифы временно недоступны";
    elements.plansDeviceLimit.textContent =
      "Актуальные тарифы появятся после обновления.";
  }

  const monthlyPlan = state.catalog.plans.find(
    (plan) => plan.code === "standard_1m"
  );
  const monthlyBasePrice = Number(monthlyPlan?.price_amount || 0);

  for (const plan of state.catalog.plans) {
    const card = document.createElement("article");
    card.className = "plan-card";

    if (plan.code === "standard_3m") {
      card.classList.add("featured");
    }

    const top = document.createElement("div");
    top.className = "plan-top";

    const name = document.createElement("p");
    name.className = "plan-name";
    name.textContent = plan.name;
    top.append(name);

    if (plan.code === "standard_3m") {
      const badge = document.createElement("span");
      badge.className = "plan-badge";
      badge.textContent = "Популярный";
      top.append(badge);
    }

    const price = document.createElement("p");
    price.className = "plan-price";
    price.textContent = formatMoney(plan.price_amount, plan.currency);

    const bottom = document.createElement("div");
    bottom.className = "plan-bottom";

    const detail = document.createElement("span");
    detail.className = "plan-detail";

    const months = Math.max(1, Math.round(plan.duration_days / 30));
    const equivalentPrice = monthlyBasePrice * months;
    const saving = Math.max(0, equivalentPrice - Number(plan.price_amount));
    const monthlyPrice = Number(plan.price_amount) / months;

    if (months > 1) {
      detail.textContent = `${formatMoney(monthlyPrice, plan.currency)}/мес`;
    } else {
      detail.textContent = `До ${plan.device_limit} устройств`;
    }

    if (months > 1 && saving > 0) {
      const savingBadge = document.createElement("span");
      savingBadge.className = "plan-saving";
      savingBadge.textContent = `Выгода ${formatMoney(saving, plan.currency)}`;
      card.append(savingBadge);
    }

    const button = document.createElement("button");
    button.className = "button button-primary";
    button.type = "button";
    button.textContent = "Выбрать";
    button.addEventListener("click", () => startPayment(plan, button));

    bottom.append(detail, button);
    card.append(top, price, bottom);
    elements.plansList.append(card);
  }
}

function renderDevices() {
  elements.devicesList.replaceChildren();
  const deviceLimit = state.me.devices.total_limit;
  const isAtLimit = deviceLimit > 0 && state.devices.length >= deviceLimit;

  elements.devicesCounter.textContent = `${state.devices.length} из ${deviceLimit}`;
  elements.deviceLimitAlert.classList.toggle("hidden", !isAtLimit);
  elements.addDeviceButton.disabled = isAtLimit;
  elements.addDeviceButton.classList.toggle("is-disabled", isAtLimit);
  elements.addDeviceButton.querySelector("span").textContent = isAtLimit
    ? "Лимит устройств исчерпан"
    : "Подключить устройство";

  if (state.devices.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty-card";

    const title = document.createElement("strong");
    title.textContent = "Нет подключённых устройств";

    const text = document.createElement("span");
    text.textContent = "Нажмите кнопку ниже, чтобы создать первое подключение.";

    empty.append(title, text);
    elements.devicesList.append(empty);
    return;
  }

  state.devices.forEach((device, index) => {
    const card = document.createElement("article");
    card.className = "device-card";

    const icon = createIcon(
      '<rect x="7" y="2.5" width="10" height="19" rx="2"/><path d="M10 18h4"/>'
    );

    const info = document.createElement("div");
    info.className = "device-info";

    const name = document.createElement("strong");
    name.textContent = `(${index + 1}/${deviceLimit}) ${device.device_name}`;

    const identifier = document.createElement("span");
    identifier.className = "device-id";
    identifier.textContent = `ID: WP-${String(device.id).padStart(6, "0")}`;

    const node = document.createElement("span");
    node.className = "device-region";
    node.textContent = `Регион: ${device.node_name}`;

    info.append(name, identifier, node);

    const removeButton = document.createElement("button");
    removeButton.className = "delete-button";
    removeButton.type = "button";
    removeButton.setAttribute("aria-label", `Удалить ${device.device_name}`);
    removeButton.innerHTML =
      '<span>Удалить</span><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M9 7V4h6v3M7 7l1 14h8l1-14M10 11v6M14 11v6"/></svg>';
    removeButton.addEventListener("click", () => {
      state.deleteDeviceId = device.id;
      elements.confirmMessage.textContent =
        `Доступ для «${device.device_name}» будет отключён.`;
      openSheet(elements.confirmSheet);
    });

    card.append(icon, info, removeButton);
    elements.devicesList.append(card);
  });
}

function renderRegion() {
  const currentRegion = state.me.current_region;
  elements.currentRegionName.textContent = currentRegion?.name
    || "Регион пока недоступен";
  elements.changeRegionButton.disabled = !currentRegion;
}

function renderLocations() {
  elements.locationsList.replaceChildren();
  const currentCode = state.me.current_region?.code;

  for (const location of state.catalog.locations) {
    const isCurrent = location.code === currentCode;
    const button = document.createElement("button");
    button.className = "location-button";
    button.type = "button";

    const text = document.createElement("span");
    const title = document.createElement("strong");
    const detail = document.createElement("span");

    title.textContent = `${isCurrent ? "✅ " : ""}${location.name}`;
    detail.textContent = isCurrent
      ? "Текущий регион"
      : location.available
        ? "Доступно"
        : "Временно недоступно";

    text.append(title, detail);
    button.append(text);
    button.disabled = !location.available || isCurrent;

    if (!button.disabled) {
      button.addEventListener("click", () => {
        changeAccountRegion(location, button);
      });
    }

    elements.locationsList.append(button);
  }
}

function renderAll() {
  renderSubscription();
  renderPayment();
  renderProfile();
  renderPlans();
  renderDevices();
  renderRegion();
  renderLocations();
}

function openSheet(sheet) {
  sheet.classList.remove("hidden");
  document.body.style.overflow = "hidden";
  haptic("medium");
}

function closeSheet(sheet) {
  sheet.classList.add("hidden");

  if (
    elements.locationSheet.classList.contains("hidden") &&
    elements.deviceSetupSheet.classList.contains("hidden") &&
    elements.regionSuccessSheet.classList.contains("hidden") &&
    elements.confirmSheet.classList.contains("hidden")
  ) {
    document.body.style.overflow = "";
  }
}

function showDeviceSetup() {
  const device = detectDevice();

  elements.detectedDeviceIcon.textContent = device.icon;
  elements.detectedDeviceName.textContent = device.name;
  elements.detectedDevicePlatform.textContent = device.platform;

  openSheet(elements.deviceSetupSheet);
}

function openExternal(url) {
  if (!url) {
    showToast("Ссылка пока недоступна.", "error");
    return;
  }

  try {
    telegram.openLink(url);
  } catch {
    window.location.href = url;
  }
}

function makeIdempotencyKey() {
  if (window.crypto?.randomUUID) {
    return `mini-app-${crypto.randomUUID()}`;
  }

  return `mini-app-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function makeClientInstanceId() {
  if (window.crypto?.randomUUID) {
    return crypto.randomUUID();
  }

  const randomPart = Math.random().toString(36).slice(2);
  return `web-${Date.now()}-${randomPart}`;
}

function getClientInstanceId() {
  if (cachedClientInstanceId) {
    return cachedClientInstanceId;
  }

  try {
    const storedId = window.localStorage.getItem(
      CLIENT_INSTANCE_STORAGE_KEY
    );

    if (
      storedId
      && storedId.length >= 16
      && storedId.length <= 64
      && /^[A-Za-z0-9._:-]+$/.test(storedId)
    ) {
      cachedClientInstanceId = storedId;
      return cachedClientInstanceId;
    }
  } catch {
    // Some embedded browsers can deny access to persistent storage.
  }

  cachedClientInstanceId = makeClientInstanceId();

  try {
    window.localStorage.setItem(
      CLIENT_INSTANCE_STORAGE_KEY,
      cachedClientInstanceId
    );
  } catch {
    // The identifier still remains stable for the current Mini App session.
  }

  return cachedClientInstanceId;
}

async function startTrial() {
  elements.trialButton.disabled = true;

  try {
    await api("/mini-app/trial", { method: "POST" });
    haptic("heavy");
    showToast("Пробный доступ активирован на 24 часа.");
    await loadData();
  } catch (error) {
    showToast(humanError(error), "error");
  } finally {
    elements.trialButton.disabled = false;
  }
}

async function startPayment(plan, button) {
  if (state.payment?.status === "pending") {
    showToast("Сначала завершите уже созданный платёж.");
    openExternal(state.payment.confirmation_url);
    return;
  }

  button.disabled = true;
  button.textContent = "Создаём…";

  try {
    state.payment = await api("/mini-app/payments", {
      method: "POST",
      body: JSON.stringify({
        plan_code: plan.code,
        idempotency_key: makeIdempotencyKey(),
      }),
    });

    renderPayment();
    haptic("medium");

    if (state.payment.confirmation_url) {
      openExternal(state.payment.confirmation_url);
    } else {
      showToast("Платёж создан. Ссылка появится после подключения оплаты.");
    }
  } catch (error) {
    showToast(humanError(error), "error");
  } finally {
    button.disabled = false;
    button.textContent = "Выбрать";
  }
}

async function changeAccountRegion(location, button) {
  button.disabled = true;

  try {
    await api("/mini-app/region", {
      method: "PATCH",
      body: JSON.stringify({
        location_code: location.code,
      }),
    });

    closeSheet(elements.locationSheet);
    haptic("heavy");
    await loadData();
    openSheet(elements.regionSuccessSheet);
  } catch (error) {
    button.disabled = false;
    showToast(humanError(error), "error");
  }
}

async function connectDevice() {
  const device = detectDevice();
  elements.confirmDeviceSetup.disabled = true;
  elements.confirmDeviceSetup.textContent = "Подключаем…";

  try {
    const result = await api("/mini-app/devices", {
      method: "POST",
      body: JSON.stringify({
        device_name: deviceDisplayName(device),
        platform: device.platform,
        client_instance_id: getClientInstanceId(),
      }),
    });

    closeSheet(elements.deviceSetupSheet);
    haptic("heavy");
    window.location.assign(result.connect_url);
  } catch (error) {
    showToast(humanError(error), "error");
  } finally {
    elements.confirmDeviceSetup.disabled = false;
    elements.confirmDeviceSetup.textContent = "Подключить устройство";
  }
}

async function removeDevice() {
  if (state.deleteDeviceId === null) {
    return;
  }

  elements.confirmDelete.disabled = true;

  try {
    await api(`/mini-app/devices/${state.deleteDeviceId}`, {
      method: "DELETE",
    });

    state.deleteDeviceId = null;
    closeSheet(elements.confirmSheet);
    haptic("heavy");
    showToast("Устройство отключено.");
    await loadData();
  } catch (error) {
    showToast(humanError(error), "error");
  } finally {
    elements.confirmDelete.disabled = false;
  }
}

async function loadData() {
  elements.refreshButton.disabled = true;

  try {
    state.me = await api("/mini-app/me");

    const [catalog, devices, payment] = await Promise.all([
      api("/mini-app/catalog"),
      api("/mini-app/devices"),
      api("/mini-app/payments/current"),
    ]);

    state.catalog = catalog;
    state.devices = devices;
    state.payment = payment;

    renderAll();
    elements.loading.classList.add("hidden");
    elements.error.classList.add("hidden");
    elements.app.classList.remove("hidden");

    if (!state.initialViewApplied) {
      const requestedView = new URLSearchParams(window.location.search).get("view");
      const allowedViews = new Set(["home", "plans", "devices", "profile"]);
      setView(allowedViews.has(requestedView) ? requestedView : "home");
      state.initialViewApplied = true;
    }

    return true;
  } catch (error) {
    elements.loading.classList.add("hidden");
    elements.app.classList.add("hidden");
    elements.errorMessage.textContent = humanError(error);
    elements.error.classList.remove("hidden");
    return false;
  } finally {
    elements.refreshButton.disabled = false;
  }
}

function initializeTelegram() {
  if (!telegram || !telegram.initData) {
    elements.loading.classList.add("hidden");
    elements.errorMessage.textContent =
      "Откройте приложение кнопкой внутри Telegram-бота Work&PlayVPN.";
    elements.error.classList.remove("hidden");
    return;
  }

  try {
    telegram.ready();
    telegram.expand();
    applyTheme();

    if (!state.telegramEventsBound) {
      telegram.BackButton?.onClick(() => setView("home"));
      telegram.onEvent?.("activated", () => loadData());
      telegram.onEvent?.("themeChanged", applyTheme);
      state.telegramEventsBound = true;
    }
  } catch {
    // Older clients can still use the core application.
  }

  loadData();
}

document.querySelectorAll("[data-view-link]").forEach((button) => {
  button.addEventListener("click", (event) => {
    event.preventDefault();
    setView(button.dataset.viewLink);
  });
});

elements.retryButton.addEventListener("click", initializeTelegram);
elements.refreshButton.addEventListener("click", async () => {
  const refreshed = await loadData();

  if (refreshed) {
    showToast("Данные обновлены.");
  }
});
elements.trialButton.addEventListener("click", startTrial);
elements.resumePaymentButton.addEventListener("click", () => {
  openExternal(state.payment?.confirmation_url);
});
elements.changeRegionButton.addEventListener("click", () => {
  openSheet(elements.locationSheet);
});
elements.addDeviceButton.addEventListener("click", () => {
  if (state.me?.subscription?.status !== "active") {
    showToast("Сначала активируйте подписку.", "error");
    setView(state.me?.trial_available ? "home" : "plans");
    return;
  }

  if (state.devices.length >= state.me.devices.total_limit) {
    showToast("Достигнут лимит устройств.", "error");
    return;
  }

  showDeviceSetup();
});
elements.closeLocationSheet.addEventListener("click", () => {
  closeSheet(elements.locationSheet);
});
elements.closeDeviceSetup.addEventListener("click", () => {
  closeSheet(elements.deviceSetupSheet);
});
elements.confirmDeviceSetup.addEventListener("click", connectDevice);
elements.regionSuccessClose.addEventListener("click", () => {
  closeSheet(elements.regionSuccessSheet);
});
elements.confirmCancel.addEventListener("click", () => {
  state.deleteDeviceId = null;
  closeSheet(elements.confirmSheet);
});
elements.confirmDelete.addEventListener("click", removeDevice);

for (const sheet of [
  elements.locationSheet,
  elements.deviceSetupSheet,
  elements.regionSuccessSheet,
  elements.confirmSheet,
]) {
  sheet.addEventListener("click", (event) => {
    if (event.target === sheet) {
      closeSheet(sheet);
    }
  });
}

document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") {
    return;
  }

  closeSheet(elements.locationSheet);
  closeSheet(elements.deviceSetupSheet);
  closeSheet(elements.regionSuccessSheet);
  closeSheet(elements.confirmSheet);
});

document.addEventListener("visibilitychange", () => {
  if (!document.hidden && !elements.app.classList.contains("hidden")) {
    loadData();
  }
});

initializeTelegram();
