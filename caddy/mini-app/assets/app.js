"use strict";

const telegram = window.Telegram?.WebApp ?? null;
const CLIENT_INSTANCE_STORAGE_KEY = "workplayvpn.client-instance.v1";
const REGION_FLAGS = Object.freeze({ NL: "🇳🇱", DE: "🇩🇪", RU: "🇷🇺", FI: "🇫🇮" });

let cachedClientInstanceId = null;

const state = {
  me: null,
  referrals: null,
  referralKey: null,
  referralLoading: false,
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
  slotSheet: document.querySelector("#slot-sheet"),
  slotOffers: document.querySelector("#slot-offers"),
  slotLimit: document.querySelector("#slot-limit"),
  locationSheet: document.querySelector("#location-sheet"),
  closeLocationSheet: document.querySelector("#close-location-sheet"),
  locationsList: document.querySelector("#locations-list"),
  deviceConnectSheet: document.querySelector("#device-connect-sheet"),
  deviceConnectList: document.querySelector("#device-connect-list"),
  closeDeviceConnect: document.querySelector("#close-device-connect"),
  connectNewDevice: document.querySelector("#connect-new-device"),
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
    "Withdrawal minimum is 500 RUB": "Минимальная сумма вывода — 500 ₽.",
    "Withdrawal already pending": "У вас уже есть заявка на вывод.",
    "Insufficient referral balance": "Недостаточно доступных средств.",
    "Withdrawal cannot be canceled": "Заявка уже обрабатывается или завершена.",
    "Withdrawal key already used": "Обновите баланс и повторите заявку.",
    "Happ encrypted import is temporarily unavailable": "Не удалось зашифровать ключ Happ. Попробуйте ещё раз позже.",
    "Invalid Happ import key": "Некорректный ключ импорта Happ. Закройте и снова откройте Mini App.",
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
  window.WorkPlayHelpAccess?.applySession(headers, path);

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
  if (name === "gifts" && typeof loadGifts === "function") loadGifts();
  if (name === "help") { loadKnowledge(); loadSupportTickets(); }
  if (name === "support") prepareSupportForm();
  if (name === "referrals") loadReferrals();
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
  prepareKeyCopyButton(tier);
}

function prepareKeyCopyButton(tier) {
  const button = document.querySelector('[data-key-action="copy"]');
  button.disabled = !preparedKeyValues.has(tier);
  button.textContent = button.disabled ? "Получаем ключ…" : "Скопировать ключ";
  const generation = keyGeneration;
  prepareSubscriptionKey(tier).then(() => {
    if (state.detailTier === tier && generation === keyGeneration) {
      button.disabled = false;
      button.textContent = "Скопировать ключ";
    }
  }).catch(() => {
    if (state.detailTier === tier && generation === keyGeneration) {
      button.disabled = false;
      button.textContent = "Повторить получение ключа";
    }
  });
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
  document.querySelectorAll("[data-key-action]").forEach((button) => { button.disabled = !entry; });
  if (entry) prepareKeyCopyButton(state.detailTier);
  document.querySelector("#header-avatar").textContent = (state.me?.user?.first_name || "W").slice(0, 1).toUpperCase();
}

function openPlanTerms(tier, returnView = "plans") {
  state.termsReturnView = returnView;
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
  document.querySelector("#terms-title").textContent = `Выберите длительность подписки · ${tierLabel(state.planTier)}`;
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

function deviceKind(device) {
  const label = `${device.happ_device_model || ""} ${device.happ_device_os || ""} ${device.device_name || ""}`.toLowerCase();
  if (/android.?tv|apple.?tv|smart.?tv|телевизор|tv\b/.test(label)) return "tv";
  if (/ipad|tablet|планшет|galaxy tab/.test(label)) return "tablet";
  if (/macbook|laptop|ноутбук|magicbook|thinkpad|notebook/.test(label)) return "laptop";
  if (/windows|macos|linux|desktop|компьютер|imac/.test(label)) return "desktop";
  if (/iphone|ios|android|phone|телефон|samsung|pixel/.test(label)) return "phone";
  return "unknown";
}

function deviceIllustration(device) {
  const image = document.createElement("img");
  image.className = "device-illustration";
  image.alt = "";
  image.setAttribute("aria-hidden", "true");
  image.width = 64;
  image.height = 64;
  image.src = `/app/assets/devices/${deviceKind(device)}.svg`;
  return image;
}

function renderDevices() {
  elements.devicesList.replaceChildren();
  const deviceLimit = state.me.devices.total_limit;
  const isAtLimit = deviceLimit > 0 && state.me.devices.active_count >= deviceLimit;

  elements.devicesCounter.textContent = `${state.me.devices.active_count} из ${deviceLimit}`;
  elements.deviceLimitAlert.classList.toggle("hidden", !isAtLimit);
  elements.addDeviceButton.disabled = !state.me.subscriptions?.length && state.me?.subscription?.status !== "active";

  state.devices.forEach((device, index) => {
    const card = document.createElement("article");
    card.className = "device-card";

    const icon = deviceIllustration(device);

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
  for (let index = state.devices.length; index < deviceLimit; index += 1) {
    const card = document.createElement("article");
    card.className = "device-card vacant-slot";
    const icon = deviceIllustration({ device_name: "unknown" });
    const info = document.createElement("div");
    info.className = "device-info";
    const name = document.createElement("strong");
    name.textContent = `(${index + 1}/${deviceLimit}) Пустой слот`;
    const hint = document.createElement("span");
    hint.textContent = "Доступен для подключения через Happ";
    info.append(name, hint);
    card.append(icon, info);
    elements.devicesList.append(card);
  }

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
    connectDevice();
  } else {
    openSheet(elements.deviceConnectSheet);
  }
}

const keySheet = document.querySelector("#key-sheet");
const keyOutput = document.querySelector("#key-output");
const keyStatus = document.querySelector("#key-sheet-status");
const keyValue = document.querySelector("#key-full-value");
const keyQR = document.querySelector("#key-qr-image");
let keyMode = "full";
let keyData = null;
let keyRequest = 0;
let keyReturnFocus = null;
const subscriptionKeys = new Map();
const preparedKeyValues = new Map();
let keyGeneration = 0;

function prepareSubscriptionKey(tier) {
  if (!subscriptionKeys.has(tier)) {
    const generation = keyGeneration;
    const pending = api(`/mini-app/keys/${tier}`, { cache: "no-store" }).then((result) => {
      if (!/^happ:\/\/crypt5\/[A-Za-z0-9_+/%=.-]+$/.test(result.url || "")) throw new ApiError(502, "Invalid Happ key");
      if (generation === keyGeneration) preparedKeyValues.set(tier, result);
      return result;
    }).catch((error) => { if (generation === keyGeneration) subscriptionKeys.delete(tier); throw error; });
    subscriptionKeys.set(tier, pending);
  }
  return subscriptionKeys.get(tier);
}

function clearKeyOutput() {
  keyRequest += 1;
  keyData = null;
  keyValue.value = "";
  keyQR.removeAttribute("src");
  keyOutput.classList.add("hidden");
  document.querySelector("#key-sheet-copy").textContent = "Скопировать ключ";
}

function closeKeySheet() {
  closeSheet(keySheet);
}

async function copyDisplayedKey(trigger = null) {
  if (!keyData) return;
  try {
    await navigator.clipboard.writeText(keyData.url);
    document.querySelector("#key-sheet-copy").textContent = "✓ Скопировано";
    if (trigger?.dataset?.keyAction === "copy") trigger.textContent = "✓ Скопировано";
    showToast("Ключ подключения скопирован.");
    haptic("light");
  } catch {
    openSheet(keySheet);
    keyOutput.classList.remove("hidden");
    keyValue.classList.remove("hidden");
    keyValue.focus();
    keyValue.select();
    keyStatus.textContent = "Буфер обмена недоступен. Выделите ключ и скопируйте вручную.";
  }
}

async function loadSubscriptionKey() {
  clearKeyOutput();
  const request = keyRequest;
  const tier = state.detailTier;
  keyStatus.textContent = "Получаем ваш ключ…";
  document.querySelector("#key-sheet-context").textContent = `${tierLabel(tier)} · Ключ подписки`;
  try {
    const result = await prepareSubscriptionKey(tier);
    if (request !== keyRequest || keySheet.classList.contains("hidden")) return;
    if (!/^happ:\/\/crypt5\/[A-Za-z0-9_+/%=.-]+$/.test(result.url || "")) {
      throw new ApiError(502, "Invalid Happ import key");
    }
    keyData = result;
    keyValue.value = result.url;
    keyValue.classList.toggle("hidden", keyMode !== "full");
    keyQR.classList.toggle("hidden", keyMode !== "qr");
    if (keyMode === "qr") keyQR.src = result.qr_data_url;
    keyOutput.classList.remove("hidden");
    keyStatus.textContent = keyMode === "qr" ? "Отсканируйте код в Happ. Один ключ для всех устройств этой подписки." : "Один ключ для всех устройств этой подписки.";
  } catch (error) {
    if (request !== keyRequest) return;
    keyStatus.textContent = humanError(error);
  }
}

function showKeySheet(mode, trigger) {
  keyMode = mode;
  keyReturnFocus = trigger;
  document.querySelector("#key-sheet-title").textContent = keyMode === "qr" ? "QR-код ключа" : keyMode === "copy" ? "Скопировать ключ" : "Полный ключ";
  openSheet(keySheet);
  document.querySelector("#key-sheet-close").focus();
  loadSubscriptionKey();
}

function handleMiniAppBack() {
  const sheet = [keySheet, elements.confirmSheet, elements.regionSuccessSheet, elements.deviceConnectSheet, elements.locationSheet, elements.slotSheet].find((item) => !item.classList.contains("hidden"));
  if (sheet) { closeSheet(sheet); return; }
  setView(state.view === "terms" ? (state.termsReturnView || "plans") : state.view === "devices" ? "subscriptions" : state.view === "support" ? "help" : "home");
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
  if (sheet === keySheet) {
    clearKeyOutput();
    keyStatus.textContent = "";
    keyReturnFocus?.focus();
    keyReturnFocus = null;
  }

  if (
    elements.locationSheet.classList.contains("hidden") &&
    elements.slotSheet.classList.contains("hidden") &&
    elements.deviceConnectSheet.classList.contains("hidden") &&
    elements.regionSuccessSheet.classList.contains("hidden") &&
    elements.confirmSheet.classList.contains("hidden") &&
    keySheet.classList.contains("hidden")
  ) {
    document.body.style.overflow = "";
  }
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

async function showSlotOffers() {
  elements.addDeviceButton.disabled = true;
  try {
    const data = await api("/mini-app/device-slots/offers");
    elements.slotLimit.textContent = `Сейчас доступно: ${data.total_limit} слотов`;
    elements.slotOffers.replaceChildren();
    for (const offer of data.offers) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "slot-offer";
      const title = document.createElement("strong");
      title.textContent = `Добавить ${offer.slots} ${offer.slots === 1 ? "устройство" : "устройства"}`;
      const price = document.createElement("span");
      price.textContent = `${formatMoney(offer.price_amount, offer.currency)} · станет ${offer.new_limit} слотов`;
      button.append(title, price);
      button.addEventListener("click", () => startPayment(offer, button));
      elements.slotOffers.append(button);
    }
    openSheet(elements.slotSheet);
  } catch (error) {
    showToast(humanError(error), "error");
  } finally {
    elements.addDeviceButton.disabled = !activeSubscriptions().length;
  }
}

async function startPayment(plan, button) {
  if (state.creatingPayment) return;
  const originalLabel = button.innerHTML;
  if (state.payment?.status === "pending") {
    showToast("Сначала завершите уже созданный платёж.");
    openExternal(state.payment.confirmation_url);
    return;
  }

  state.creatingPayment = true;
  button.disabled = true;
  button.textContent = "Создаём…";

  try {
    state.payment = await api("/mini-app/payments", {
      method: "POST",
      body: JSON.stringify({
        plan_code: plan.code,
        idempotency_key: button.dataset.paymentKey || (button.dataset.paymentKey = makeIdempotencyKey()),
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
    state.creatingPayment = false;
    button.innerHTML = originalLabel;
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
  elements.connectNewDevice.disabled = true;
  elements.connectNewDevice.textContent = "Подключаем…";

  try {
    const result = await api("/mini-app/devices", {
      method: "POST",
      body: JSON.stringify({
        device_name: deviceDisplayName(device),
        platform: device.platform,
        client_instance_id: getClientInstanceId(),
      }),
    });

    closeSheet(elements.deviceConnectSheet);
    haptic("heavy");
    window.location.assign(state.detailTier === "mobile"
      ? result.mobile_connect_url || result.connect_url
      : result.connect_url);
  } catch (error) {
    showToast(humanError(error), "error");
  } finally {
    elements.connectNewDevice.disabled = false;
    elements.connectNewDevice.textContent = "Подключить новое устройство";
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
  keyGeneration += 1;
  subscriptionKeys.clear();
  preparedKeyValues.clear();
  clearKeyOutput();
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
    if (state.view === "referrals") loadReferrals();
    if (state.view === "gifts" && typeof loadGifts === "function") loadGifts();
    elements.loading.classList.add("hidden");
    elements.error.classList.add("hidden");
    if (!state.initialViewApplied) {
      elements.app.classList.add("app-intro");
    }
    elements.app.classList.remove("hidden");

    if (!state.initialViewApplied) {
      const params = new URLSearchParams(window.location.search);
      const requestedView = params.get("view");
      const allowedViews = new Set(["home", "plans", "devices", "profile", "subscriptions", "referrals", "help", "support", "gifts"]);
      setView(allowedViews.has(requestedView) ? requestedView : "home");
      state.initialViewApplied = true;
      const keyTier = params.get("key_tier");
      if (params.get("key_action") === "copy" && ["basic", "mobile"].includes(keyTier)
          && activeSubscriptions().some((entry) => subscriptionTier(entry) === keyTier)) {
        openSubscription(keyTier);
        showKeySheet("copy", document.querySelector('[data-key-action="copy"]'));
      }
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
      telegram.BackButton?.onClick(handleMiniAppBack);
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
  openPlanTerms(state.detailTier, "devices");
});

elements.addDeviceButton.addEventListener("click", showSlotOffers);
document.querySelector("#close-slot-sheet").addEventListener("click", () => closeSheet(elements.slotSheet));
elements.closeDeviceConnect.addEventListener("click", () => closeSheet(elements.deviceConnectSheet));
elements.connectNewDevice.addEventListener("click", connectDevice);
elements.closeLocationSheet.addEventListener("click", () => {
  closeSheet(elements.locationSheet);
});
elements.regionSuccessClose.addEventListener("click", () => {
  closeSheet(elements.regionSuccessSheet);
});
elements.confirmCancel.addEventListener("click", () => {
  state.deleteDeviceId = null;
  closeSheet(elements.confirmSheet);
});
elements.confirmDelete.addEventListener("click", removeDevice);

for (const sheet of [
  keySheet,
  elements.locationSheet,
  elements.slotSheet,
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

  closeKeySheet();
  closeSheet(elements.locationSheet);
  closeSheet(elements.slotSheet);
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

function referralMoney(kopecks) { return new Intl.NumberFormat("ru-RU", {style:"currency",currency:"RUB",minimumFractionDigits:2,maximumFractionDigits:2}).format(kopecks / 100); }
const referralStatus = {requested:"Ожидает обработки",processing:"В обработке",paid:"Выплачено",rejected:"Отклонено",canceled:"Отменено"};
function referralNode(tag, text, className = "") {
  const node = document.createElement(tag); node.textContent = text; node.className = className; return node;
}
function renderReferrals() {
  const data=state.referrals;
  if (!data) return;
  document.querySelector("#referral-balance").textContent = referralMoney(data.available_kopecks) + " доступно";
  document.querySelector("#referral-stats").textContent = `Приглашено: ${data.invited_count} · Оплатили: ${data.paying_count}`;
  document.querySelector("#referral-reserved").textContent = data.reserved_kopecks ? `В заявках: ${referralMoney(data.reserved_kopecks)}` : data.balance_kopecks < 0 ? `Корректировка после возвратов: ${referralMoney(data.balance_kopecks)}` : "Вывод от 500 ₽ на личную карту";
  document.querySelector("#referral-mode").textContent = data.live_payments ? "" : "Оплата сейчас в тестовом режиме. Тестовые покупки не приносят денежного вознаграждения.";
  document.querySelector("#referral-link").value=data.link;
  document.querySelector("#referral-copy").disabled=false;
  document.querySelector("#referral-share").disabled=false;
  document.querySelector("#referral-withdraw").disabled=data.available_kopecks < data.minimum_kopecks || data.reserved_kopecks>0;
  const history=document.querySelector("#referral-commissions");history.replaceChildren();
  if (!data.commissions.length) history.append(referralNode("p","Начислений пока нет. Поделись своей ссылкой с друзьями."));
  for(const row of data.commissions) {
    const item=referralNode("article","","referral-history-row");
    item.append(referralNode("strong",referralMoney(row.amount_kopecks-row.reversed_kopecks)),referralNode("span",`Оплата №${row.payment_id} · ${formatDate(row.created_at)}`));
    if(row.reversed_kopecks) item.append(referralNode("span",`Возврат: −${referralMoney(row.reversed_kopecks)}`));
    history.append(item);
  }
  const requests=document.querySelector("#referral-withdrawals");requests.replaceChildren();
  if(!data.withdrawals.length) requests.append(referralNode("p","Заявок на вывод пока нет."));
  for(const row of data.withdrawals) {
    const item=referralNode("article","","referral-history-row");
    item.append(referralNode("strong",`${referralMoney(row.amount_kopecks)} · ${referralStatus[row.status] || row.status}`),referralNode("span",`№${row.id} · ${formatDate(row.created_at)}`));
    if(row.note) item.append(referralNode("p",row.note));
    if(["requested","processing"].includes(row.status)) {
      const contact=referralNode("button","Согласовать выплату","button button-secondary");contact.type="button";
      contact.addEventListener("click",()=>{ navigator.clipboard?.writeText(row.id).catch(()=>{});openBotLink("https://t.me/workplayvpnteam"); });item.append(contact);
    }
    if(row.status==="requested") {
      const button=referralNode("button","Отменить заявку","button button-secondary");button.type="button";
      button.addEventListener("click",async()=>{
        button.disabled=true;
        try {await api(`/mini-app/referrals/withdrawals/${row.id}/cancel`,{method:"POST"}); await loadReferrals();showToast("Заявка отменена.");}
        catch(error){showToast(humanError(error),"error");button.disabled=false;}
      });item.append(button);
    }
    requests.append(item);
  }
}
async function loadReferrals() {
  if(state.referralLoading) return;
  state.referralLoading=true;
  document.querySelector("#referral-error").textContent="";
  try {state.referrals=await api("/mini-app/referrals");renderReferrals();}
  catch(error){document.querySelector("#referral-error").textContent=humanError(error);document.querySelector("#referral-balance").textContent="Баланс временно недоступен";document.querySelector("#referral-withdraw").disabled=true;}
  finally {state.referralLoading=false;}
}
document.querySelector("#referral-refresh").addEventListener("click",loadReferrals);
document.querySelector("#referral-copy").addEventListener("click",async()=>{
  try {await navigator.clipboard.writeText(state.referrals.link);showToast("Ссылка скопирована.");}
  catch {document.querySelector("#referral-link").select();showToast("Выдели и скопируй ссылку.");}
});
document.querySelector("#referral-share").addEventListener("click",()=>{
  const link=state.referrals?.link;if(!link)return;
  openBotLink(`https://t.me/share/url?url=${encodeURIComponent(link)}&text=${encodeURIComponent("Work&PlayVPN — для работы, игр и любимого досуга. Попробуй Basic на 24 часа, если ещё не пользовался сервисом.")}`);
});
document.querySelector("#referral-withdraw-form").addEventListener("submit",async(event)=>{
  event.preventDefault();
  const raw=document.querySelector("#referral-amount").value.trim().replace(",",".");
  if(!/^\d{1,8}(\.\d{1,2})?$/.test(raw)){showToast("Укажи сумму в рублях, например 500,00.","error");return;}
  const [rub,coins=""]=raw.split(".");const amount=Number(rub)*100+Number(coins.padEnd(2,"0"));
  if(amount<50000){showToast("Минимальная сумма — 500 ₽.","error");return;}
  const button=document.querySelector("#referral-withdraw");button.disabled=true;
  if(!state.referralKey) state.referralKey=makeIdempotencyKey();
  try {
    await api("/mini-app/referrals/withdrawals",{method:"POST",body:JSON.stringify({amount_kopecks:amount,idempotency_key:state.referralKey})});
    state.referralKey=null;document.querySelector("#referral-amount").value="";
    await loadReferrals();showToast("Заявка создана. Согласуй выплату с поддержкой.");
  }catch(error){if(error instanceof ApiError && error.status>=400 && error.status<500)state.referralKey=null;showToast(humanError(error),"error");button.disabled=false;}
});

initializeTelegram();


// Key values stay in memory and are discarded whenever the dialog closes.
document.querySelectorAll("[data-key-action]").forEach((button) => {
  button.addEventListener("click", () => {
    const data = preparedKeyValues.get(state.detailTier);
    if (button.dataset.keyAction === "copy" && data) {
      keyData = data;
      keyValue.value = data.url;
      keyReturnFocus = button;
      copyDisplayedKey(button);
    } else showKeySheet(button.dataset.keyAction, button);
  });
});
document.querySelector("#key-sheet-close").addEventListener("click", closeKeySheet);
document.querySelector("#key-sheet-done").addEventListener("click", closeKeySheet);
document.querySelector("#key-sheet-copy").addEventListener("click", () => copyDisplayedKey());
document.querySelector("#key-sheet-happ").addEventListener("click", () => { if (keyData) window.location.href = keyData.url; });
keySheet.addEventListener("keydown", (event) => {
  if (event.key !== "Tab") return;
  const controls = [...keySheet.querySelectorAll("button, textarea")].filter((item) => !item.disabled && item.getClientRects().length);
  const first = controls[0];
  const last = controls[controls.length - 1];
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
});
