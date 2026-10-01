"use strict";

const telegram = window.Telegram?.WebApp ?? null;
const CLIENT_INSTANCE_STORAGE_KEY = "workplayvpn.client-instance.v1";
const REGION_FLAGS = Object.freeze({ NL: "🇳🇱", DE: "🇩🇪", RU: "🇷🇺", FI: "🇫🇮" });

let cachedClientInstanceId = null;

const state = {
  me: null,
  catalog: null,
  planTier: "basic",
  detailTier: "basic",
  view: "home",
  devices: [],
  payment: null,
  deleteDeviceId: null,
  toastTimer: null,
  telegramEventsBound: false,
  initialViewApplied: false,
};

const THEMES = {
  dark: {
    header: "#0b1118",
    background: "#0b1118",
    bottomBar: "#0b1118",
  },
  light: {
    header: "#f2f6f5",
    background: "#f2f6f5",
    bottomBar: "#f2f6f5",
  },
};

const elements = {
  loading: document.querySelector("#loading-screen"),
  error: document.querySelector("#error-screen"),
  errorMessage: document.querySelector("#error-message"),
  app: document.querySelector("#app"),
  retryButton: document.querySelector("#retry-button"),
  reopenBotButton: document.querySelector("#reopen-bot-button"),
  openBotLink: document.querySelector("#open-bot-link"),
  refreshButton: document.querySelector("#refresh-button"),
  firstName: document.querySelector("#user-first-name"),
  subscriptionCard: document.querySelector("#subscription-card"),
  subscriptionLabel: document.querySelector("#subscription-label"),
  subscriptionTitle: document.querySelector("#subscription-title"),
  subscriptionDescription: document.querySelector("#subscription-description"),
  subscriptionExpiry: document.querySelector("#subscription-expiry"),
  subscriptionProfiles: document.querySelector("#subscription-profiles"),
  deviceSummary: document.querySelector("#device-summary"),
  pendingPayment: document.querySelector("#pending-payment"),
  pendingPaymentAmount: document.querySelector("#pending-payment-amount"),
  resumePaymentButton: document.querySelector("#resume-payment-button"),
  trialButton: document.querySelector("#trial-button"),
  plansList: document.querySelector("#plans-list"),
  plansTierDescription: document.querySelector("#plans-tier-description"),
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
  deviceConnectSheet: document.querySelector("#device-connect-sheet"),
  deviceConnectList: document.querySelector("#device-connect-list"),
  closeDeviceConnect: document.querySelector("#close-device-connect"),
  connectNewDevice: document.querySelector("#connect-new-device"),
  closeDeviceSetup: document.querySelector("#close-device-setup"),
  detectedDeviceIcon: document.querySelector("#detected-device-icon"),
  detectedDeviceName: document.querySelector("#detected-device-name"),
  detectedDevicePlatform: document.querySelector("#detected-device-platform"),
  deviceModelInput: document.querySelector("#device-model-input"),
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
    "Changing access tier requires a separate upgrade flow": "Смена версии во время действующей подписки пока недоступна.",
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

function isSessionError(error) {
  return error instanceof ApiError && error.status === 401;
}

function showLoadError(error) {
  const sessionExpired = isSessionError(error);
  elements.loading.classList.add("hidden");
  elements.app.classList.add("hidden");
  elements.errorMessage.textContent = sessionExpired
    ? "Сеанс Telegram истёк. Откройте бота и снова запустите Mini App, чтобы войти заново."
    : humanError(error);
  elements.retryButton.classList.toggle("hidden", sessionExpired);
  elements.reopenBotButton.classList.toggle("hidden", !sessionExpired || !telegram?.close);
  elements.openBotLink.classList.toggle("hidden", sessionExpired && !!telegram?.close);
  elements.error.classList.remove("hidden");
}

function initDataIsStale() {
  const rawDate = new URLSearchParams(telegram?.initData || "").get("auth_date");
  if (!rawDate) return false;
  const timestamp = Number(rawDate);
  return Number.isFinite(timestamp) && Date.now() / 1000 - timestamp > 300;
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

    const error = new ApiError(response.status, detail);
    if (isSessionError(error)) showLoadError(error);
    throw error;
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
  if (name === "devices") {
    if (!activeSubscriptions().some((entry) => subscriptionTier(entry) === state.detailTier)) {
      state.detailTier = subscriptionTier(activeSubscriptions()[0] || {});
    }
    renderSubscriptionDetail();
  }
  state.view = name;
  document.querySelectorAll(".view").forEach((view) => {
    view.classList.toggle("active", view.id === `view-${name}`);
  });

  document.querySelectorAll(".nav-item").forEach((button) => {
    button.classList.toggle("active", button.dataset.viewLink === (name === "devices" ? "subscriptions" : name === "terms" ? "plans" : name));
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

function subscriptionTier(entry) {
  return entry.access_tier || (entry.plan_code?.startsWith("mobile_") ? "mobile" : "basic");
}

function tierLabel(tier) { return tier === "mobile" ? "Mobile" : "Basic"; }

function activeSubscriptions() {
  const entries = state.me?.subscriptions?.filter((entry) => entry.status === "active") || [];
  return entries.length ? entries : (state.me?.subscription?.status === "active" ? [state.me.subscription] : []);
}

function openSubscription(tier) {
  state.detailTier = tier;
  setView("devices");
}

function renderSubscriptionCards(container, entries) {
  container.replaceChildren();
  if (!entries.length) {
    const note = document.createElement("p");
    note.className = "shared-note";
    note.textContent = "Пока нет активной подписки. Выбери подходящий тариф в каталоге.";
    container.append(note);
  }
  for (const entry of entries) {
    const tier = subscriptionTier(entry);
    const card = document.createElement("button");
    card.type = "button";
    card.className = `subscription-tile subscription-tile-${tier}`;
    const title = document.createElement("strong");
    title.textContent = tierLabel(tier);
    const badge = document.createElement("span");
    badge.className = "tier-badge";
    badge.textContent = "Активна";
    const description = document.createElement("span");
    description.className = "tile-description";
    description.textContent = tier === "mobile" ? "Wi-Fi и мобильная сеть" : "Для работы и досуга";
    const date = document.createElement("span");
    date.className = "tile-date";
    date.textContent = `До ${formatDate(entry.expires_at)} · Открыть →`;
    card.append(title, badge, description, date);
    card.addEventListener("click", () => openSubscription(tier));
    container.append(card);
  }
}

function renderSubscriptionDetail() {
  const entry = activeSubscriptions().find((item) => subscriptionTier(item) === state.detailTier);
  document.querySelector("#detail-tier-name").textContent = tierLabel(state.detailTier);
  document.querySelector("#detail-expiry").textContent = entry ? formatDate(entry.expires_at) : "Неактивна";
  document.querySelector("#detail-description").textContent = state.detailTier === "mobile"
    ? "Подключение для Wi-Fi и мобильной сети." : "Подключение для работы и любимого досуга.";
  document.querySelector("#detail-connect").disabled = !entry;
  document.querySelector("#header-avatar").textContent = (state.me?.user?.first_name || "W").slice(0, 1).toUpperCase();
}

function openPlanTerms(tier) {
  if (!state.catalog.plans.some((plan) => (plan.access_tier || "basic") === tier)) {
    showToast("Эта подписка сейчас недоступна.", "error");
    setView("plans");
    return;
  }
  state.planTier = tier;
  renderPlans();
  setView("terms");
}

function mobileRouteDescription() {
  return Object.keys(state.me?.auto_connect_urls || {}).length
    ? "Прямой и резервный маршруты. Выбор маршрута автоматический."
    : "Прямой маршрут и резерв через CDN. Нужный профиль выбирается в Happ.";
}

function renderCatalogOverview() {
  const container = document.querySelector("#catalog-overview");
  container.replaceChildren();
  const availableTiers = [];
  for (const tier of ["basic", "mobile"]) {
    const plans = state.catalog.plans.filter((plan) => (plan.access_tier || "basic") === tier);
    if (!plans.length) continue;
    availableTiers.push(tier);
    const card = document.createElement("article");
    card.className = `catalog-card catalog-card-${tier}`;
    const heading = document.createElement("div");
    heading.className = "catalog-card-heading";
    const title = document.createElement("h2");
    title.textContent = tierLabel(tier);
    const badge = document.createElement("span");
    badge.className = "tier-badge";
    badge.textContent = tier === "mobile" ? "Больше маршрутов" : "На каждый день";
    heading.append(title, badge);
    const description = document.createElement("p");
    description.textContent = tier === "mobile"
      ? "Для тех, кто пользуется и Wi-Fi, и мобильным интернетом: рабочие задачи, игры и видео с дополнительным вариантом подключения."
      : "Для работы и отдыха в обычной сети: созвоны, сайты, игры, видео и любимые сервисы через прямое VPN-подключение.";
    const features = document.createElement("ul");
    features.className = "catalog-features";
    for (const text of [
      tier === "mobile" ? mobileRouteDescription() : "Прямое подключение. При ограничениях мобильной сети может быть недоступно.",
      "Подключение через приложение Happ.",
      `До ${Math.max(...plans.map((plan) => plan.device_limit))} устройств в тарифе. Лимит общий с другой подпиской.`,
      tier === "mobile" ? "Можно использовать вместе с Basic — сроки подписок независимы." : "Можно использовать вместе с Mobile — сроки подписок независимы.",
    ]) {
      const item = document.createElement("li");
      item.textContent = text;
      features.append(item);
    }
    const button = document.createElement("button");
    button.type = "button";
    button.className = `button ${tier === "mobile" ? "button-primary" : "button-secondary"} button-wide`;
    button.textContent = `Выбрать срок ${tierLabel(tier)} →`;
    button.addEventListener("click", () => openPlanTerms(tier));
    card.append(heading, description, features, button);
    if (activeSubscriptions().some((entry) => subscriptionTier(entry) === tier)) {
      const manage = document.createElement("button");
      manage.type = "button";
      manage.className = "text-button catalog-manage";
      manage.textContent = `Моя подписка ${tierLabel(tier)} →`;
      manage.addEventListener("click", () => openSubscription(tier));
      card.append(manage);
    }
    container.append(card);
  }
  const comparison = document.querySelector("#catalog-comparison");
  comparison.replaceChildren();
  if (availableTiers.length < 2) return;
  const heading = document.createElement("h2");
  heading.textContent = "Чем отличаются";
  const wrap = document.createElement("div");
  wrap.className = "comparison-wrap";
  const table = document.createElement("table");
  table.className = "comparison-table";
  const caption = document.createElement("caption");
  caption.textContent = "Сравнение Basic и Mobile";
  table.append(caption);
  const thead = document.createElement("thead");
  const header = document.createElement("tr");
  for (const label of ["Возможности", "Basic", "Mobile"]) {
    const th = document.createElement("th"); th.scope = "col"; th.textContent = label; header.append(th);
  }
  thead.append(header); table.append(thead);
  const tbody = document.createElement("tbody");
  for (const values of [
    ["Подключение", "Через Happ", "Через Happ"],
    ["Прямой маршрут", "Да", "Да"],
    ["Резерв через CDN", "Нет", "Да"],
    ["При ограничениях сети", "Может быть недоступно", "Можно попробовать резерв"],
    ["Устройства", "Общий лимит", "Общий лимит"],
    ["Срок действия", "Отдельный", "Отдельный"],
  ]) {
    const row = document.createElement("tr");
    values.forEach((value, index) => {
      const cell = document.createElement(index === 0 ? "th" : "td");
      if (index === 0) cell.scope = "row";
      cell.textContent = value; row.append(cell);
    });
    tbody.append(row);
  }
  table.append(tbody); wrap.append(table);
  const note = document.createElement("p");
  note.className = "shared-note";
  note.textContent = "Работа подключения зависит от сети и её ограничений. Резервный маршрут не гарантирует доступ в любой ситуации.";
  comparison.append(heading, wrap, note);
}

function renderSubscription() {
  const { subscription, devices } = state.me;
  const entries = activeSubscriptions();
  const isActive = entries.length > 0;
  renderSubscriptionCards(elements.subscriptionProfiles, entries);
  renderSubscriptionCards(document.querySelector("#subscriptions-list"), entries);

  elements.subscriptionCard.classList.toggle("is-active", isActive);
  elements.deviceSummary.textContent =
    `${devices.active_count} из ${devices.total_limit}`;

  if (isActive) {
    elements.subscriptionLabel.textContent = "Подписка активна";
    elements.subscriptionTitle.textContent = entries.length > 1
      ? "Две подписки активны" : entries[0].plan_name || tierLabel(subscriptionTier(entries[0]));
    elements.subscriptionDescription.textContent = entries.length > 1
      ? "Обычный VPN и Mobile действуют каждый до своего срока."
      : "Защищённое подключение доступно на ваших устройствах.";
    elements.subscriptionExpiry.textContent = entries.length > 1
      ? "Отдельно для каждой" : formatDate(entries[0].expires_at);
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
    && !isActive
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
    (state.me.subscriptions || []).length > 0
      ? state.me.subscriptions.map((entry) => entry.access_tier === "mobile"
        ? "Mobile" : "Work&PlayVPN").join(" + ")
      : subscription?.status === "active" ? subscription.plan_name : "Не активна";
  elements.profileDevices.textContent =
    `${state.me.devices.active_count} из ${state.me.devices.total_limit}`;
}

function renderPlans() {
  elements.plansList.replaceChildren();
  const availableTiers = new Set(
    state.catalog.plans.map((plan) => plan.access_tier || "basic")
  );
  if (!availableTiers.has(state.planTier)) {
    state.planTier = availableTiers.has("mobile") && !availableTiers.has("basic")
      ? "mobile" : "basic";
  }
  document.querySelector("#terms-title").textContent = `Выбери срок ${tierLabel(state.planTier)}`;
  elements.plansTierDescription.textContent = state.planTier === "mobile"
    ? (Object.keys(state.me?.auto_connect_urls || {}).length
      ? "Подключение для Wi-Fi и мобильной сети. Маршрут выбирается автоматически."
      : "Прямое подключение и резерв через CDN. При смене сети выберите нужный профиль в Happ.")
    : "Прямое подключение. При ограничениях мобильной сети может быть недоступно.";
  const plans = state.catalog.plans.filter(
    (plan) => (plan.access_tier || "basic") === state.planTier
  );

  if (state.catalog.plans.length > 0) {
    const cheapestPlan = state.catalog.plans.reduce((cheapest, plan) => (
      Number(plan.price_amount) < Number(cheapest.price_amount)
        ? plan
        : cheapest
    ));
    elements.plansStartingPrice.textContent =
      `От ${formatMoney(cheapestPlan.price_amount, cheapestPlan.currency)} `
      + `за ${cheapestPlan.name.toLowerCase()}`;
  } else {
    elements.plansStartingPrice.textContent = "Тарифы временно недоступны";
  }

  if (plans.length > 0) {
    const deviceLimit = Math.max(...plans.map((plan) => plan.device_limit));
    elements.plansDeviceLimit.textContent =
      `В каждом тарифе доступно до ${deviceLimit} устройств.`;
  } else {
    elements.plansDeviceLimit.textContent =
      "Актуальные тарифы появятся после обновления.";
  }

  const monthlyPlan = plans.find(
    (plan) => plan.duration_days === 30
  );
  const monthlyBasePrice = Number(monthlyPlan?.price_amount || 0);

  for (const plan of plans) {
    const card = document.createElement("article");
    card.className = "plan-card";

    if (plan.duration_days === 90) {
      card.classList.add("featured");
    }

    const top = document.createElement("div");
    top.className = "plan-top";

    const name = document.createElement("p");
    name.className = "plan-name";
    name.textContent = plan.name;
    top.append(name);

    if (plan.duration_days === 90) {
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
  const isAtLimit = deviceLimit > 0 && state.me.devices.active_count >= deviceLimit;

  elements.devicesCounter.textContent = `${state.me.devices.active_count} из ${deviceLimit}`;
  elements.deviceLimitAlert.classList.toggle("hidden", !isAtLimit);
  elements.addDeviceButton.disabled = !state.me.subscriptions?.length && state.me?.subscription?.status !== "active";

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
    const deviceLabel = device.happ_device_model && device.happ_device_os
      ? `${device.happ_device_model} (${device.happ_device_os})`
      : device.device_name;
    name.textContent = `(${index + 1}/${deviceLimit}) ${deviceLabel}`;

    const identifier = document.createElement("span");
    identifier.className = "device-id";
    identifier.textContent = `ID: ${device.public_id}`;

    info.append(name, identifier);

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

function showDeviceConnections() {
  elements.deviceConnectList.replaceChildren();
  for (const device of state.devices) {
    const links = [
      ["Basic", state.me.basic_device_connect_urls?.[device.id]],
      ["Mobile", state.me.auto_connect_urls?.[device.id]],
    ].filter(([tier, url]) => Boolean(url) && tier.toLowerCase() === state.detailTier);
    if (!links.length) continue;

    const entry = document.createElement("div");
    entry.className = "device-connect-entry";
    const title = document.createElement("strong");
    title.textContent = device.happ_device_model && device.happ_device_os
      ? `${device.happ_device_model} (${device.happ_device_os})`
      : device.device_name;
    entry.append(title);
    for (const [tier, url] of links) {
      const link = document.createElement("a");
      link.className = "button button-secondary";
      link.textContent = `Открыть ${tier} в HAPP`;
      link.href = url;
      entry.append(link);
    }
    elements.deviceConnectList.append(entry);
  }
  // Accounts outside the automatic-routing pilot retain their existing Mobile link.
  if (!elements.deviceConnectList.childElementCount && state.devices.length && state.detailTier === "mobile" && state.me.connect_urls?.mobile) {
    const link = document.createElement("a");
    link.className = "button button-secondary";
    link.textContent = "Открыть Mobile в Happ";
    link.href = state.me.connect_urls.mobile;
    elements.deviceConnectList.append(link);
  }
  const canAdd = state.me.devices.active_count < state.me.devices.total_limit;
  elements.connectNewDevice.classList.toggle("hidden", !canAdd);
  if (!elements.deviceConnectList.childElementCount && !canAdd) {
    const message = document.createElement("p");
    message.className = "setup-note";
    message.textContent = "Нет доступных ссылок. Освободите место или обновите подписку и попробуйте снова.";
    elements.deviceConnectList.append(message);
  }
  if (!elements.deviceConnectList.childElementCount && canAdd) {
    showDeviceSetup();
  } else {
    openSheet(elements.deviceConnectSheet);
  }
}

function renderRegion() {
  const currentRegion = state.me.current_region;
  const icon = elements.changeRegionButton.querySelector(".region-card-icon");
  icon.textContent = REGION_FLAGS[currentRegion?.code] || "📍";
  elements.currentRegionName.textContent = currentRegion?.name
    || "Регион пока недоступен";
  elements.changeRegionButton.disabled = !currentRegion;
}

function renderLocations() {
  elements.locationsList.replaceChildren();
  const currentCode = state.me.current_region?.code;

  for (const location of state.catalog.locations) {
    if (!REGION_FLAGS[location.code]) continue;
    const isCurrent = location.code === currentCode;
    const button = document.createElement("button");
    button.className = "location-button";
    button.type = "button";

    const text = document.createElement("span");
    const title = document.createElement("strong");
    const detail = document.createElement("span");

    title.textContent = `${REGION_FLAGS[location.code]} ${location.name}${isCurrent ? " ✓" : ""}`;
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
  renderSubscriptionDetail();
  renderCatalogOverview();
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
    elements.deviceConnectSheet.classList.contains("hidden") &&
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
  elements.deviceModelInput.value = device.name;

  openSheet(elements.deviceSetupSheet);
}

function openBotLink(url) {
  if (telegram?.openTelegramLink) {
    try {
      telegram.openTelegramLink(url);
      // Modern clients can keep the Mini App over the chat; reveal the destination.
      try { telegram.close?.(); } catch { /* The Telegram link still opens. */ }
      return;
    } catch { /* Older clients retain ordinary URL navigation. */ }
  }
  window.location.href = url;
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
  const model = elements.deviceModelInput.value.trim().replace(/\s+/g, " ");
  if (!model || model.length > 65) {
    showToast("Укажите модель устройства (до 65 символов).", "error");
    elements.deviceModelInput.focus();
    return;
  }
  device.name = model;
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
    window.location.assign(state.detailTier === "mobile"
      ? result.mobile_connect_url || result.connect_url
      : result.connect_url);
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
    if (initDataIsStale()) {
      throw new ApiError(401, "Telegram Mini App credentials expired");
    }
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
    if (!state.initialViewApplied) {
      elements.app.classList.add("app-intro");
    }
    elements.app.classList.remove("hidden");

    if (!state.initialViewApplied) {
      const requestedView = new URLSearchParams(window.location.search).get("view");
      const allowedViews = new Set(["home", "plans", "devices", "profile", "subscriptions", "referrals"]);
      setView(allowedViews.has(requestedView) ? requestedView : "home");
      state.initialViewApplied = true;
    }

    return true;
  } catch (error) {
    showLoadError(error);
    return false;
  } finally {
    elements.refreshButton.disabled = false;
  }
}

function initializeTelegram() {
  if (!telegram || !telegram.initData) {
    elements.loading.classList.add("hidden");
    elements.retryButton.classList.add("hidden");
    elements.reopenBotButton.classList.add("hidden");
    elements.openBotLink.classList.remove("hidden");
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
      telegram.BackButton?.onClick(() => setView(state.view === "terms" ? "plans" : state.view === "devices" ? "subscriptions" : "home"));
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
elements.reopenBotButton.addEventListener("click", () => {
  try {
    telegram.close();
  } catch {
    elements.reopenBotButton.classList.add("hidden");
    elements.openBotLink.classList.remove("hidden");
  }
});
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
document.querySelector("#detail-connect").addEventListener("click", showDeviceConnections);
document.querySelector("#detail-renew").addEventListener("click", () => {
  openPlanTerms(state.detailTier);
});

elements.addDeviceButton.addEventListener("click", () => {
  if (!activeSubscriptions().length) {
    showToast("Сначала активируйте подписку.", "error");
    setView(state.me?.trial_available ? "home" : "plans");
    return;
  }

  showDeviceConnections();
});
elements.closeDeviceConnect.addEventListener("click", () => closeSheet(elements.deviceConnectSheet));
elements.connectNewDevice.addEventListener("click", () => {
  closeSheet(elements.deviceConnectSheet);
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
  elements.deviceConnectSheet,
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
  closeSheet(elements.deviceConnectSheet);
  closeSheet(elements.regionSuccessSheet);
  closeSheet(elements.confirmSheet);
});

document.addEventListener("visibilitychange", () => {
  if (!document.hidden && !elements.app.classList.contains("hidden")) {
    loadData();
  }
});

document.querySelectorAll('a[href^="https://t.me/"]').forEach((link) => {
  link.addEventListener("click", (event) => {
    event.preventDefault();
    openBotLink(link.href);
  });
});

initializeTelegram();
