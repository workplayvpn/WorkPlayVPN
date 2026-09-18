"use strict";

function detectPlatform() {
    const userAgent = navigator.userAgent || "";
    const platform = navigator.platform || "";

    if (/iPhone/i.test(userAgent)) {
        return {deviceName: "iPhone", platform: "iOS", icon: "📱"};
    }

    if (
        /iPad/i.test(userAgent)
        || (/Macintosh/i.test(userAgent) && navigator.maxTouchPoints > 1)
    ) {
        return {deviceName: "iPad", platform: "iPadOS", icon: "▣"};
    }

    if (/Android/i.test(userAgent)) {
        return {deviceName: "Android", platform: "Android", icon: "🤖"};
    }

    if (/Windows/i.test(userAgent)) {
        return {deviceName: "Windows PC", platform: "Windows", icon: "▦"};
    }

    if (/Macintosh|Mac OS X/i.test(userAgent)) {
        return {deviceName: "Mac", platform: "macOS", icon: "◆"};
    }

    if (/Linux/i.test(platform)) {
        return {deviceName: "Linux PC", platform: "Linux", icon: "🐧"};
    }

    return {deviceName: "Устройство", platform: "Unknown", icon: "📱"};
}

function friendlyError(detail) {
    const errors = {
        "Activation already used": [
            "Ссылка уже использована",
            "Создайте новую ссылку подключения в Telegram-боте.",
        ],
        "Activation expired": [
            "Ссылка устарела",
            "Вернитесь в Telegram-бот и создайте новую ссылку.",
        ],
        "Activation not found": [
            "Ссылка недействительна",
            "Получите новую ссылку подключения в Telegram-боте.",
        ],
        "Device limit reached": [
            "Достигнут лимит устройств",
            "Отключите ненужное устройство или добавьте новый слот.",
        ],
        "Active subscription required": [
            "Нужна активная подписка",
            "Выберите тариф Work&PlayVPN и повторите подключение.",
        ],
        "Subscription expired": [
            "Подписка закончилась",
            "Продлите подписку и повторите подключение.",
        ],
        "VPN node unavailable": [
            "Сервер временно недоступен",
            "Попробуйте подключить устройство немного позже.",
        ],
    };

    return errors[detail] || [
        "Не удалось подключить устройство",
        "Попробуйте ещё раз или создайте новую ссылку в Telegram-боте.",
    ];
}

function showError(title, text) {
    document.getElementById("activation").hidden = true;
    document.getElementById("error-title").textContent = title;
    document.getElementById("error-text").textContent = text;
    document.getElementById("error-block").hidden = false;
}

document.addEventListener("DOMContentLoaded", () => {
    const app = document.getElementById("activation-app");
    const token = app?.dataset.activationToken || "";
    const device = detectPlatform();
    const activateButton = document.getElementById("activate-button");
    const copyButton = document.getElementById("copy-button");

    document.getElementById("device-info").textContent =
        "Мы определили устройство и готовы создать безопасный доступ.";
    document.getElementById("device-name").textContent = device.deviceName;
    document.getElementById("device-platform").textContent = device.platform;
    document.querySelector(".device-icon").textContent = device.icon;

    activateButton.addEventListener("click", async () => {
        activateButton.disabled = true;
        activateButton.textContent = "Подключаем…";

        try {
            const response = await fetch(
                `/device-activations/${encodeURIComponent(token)}/complete`,
                {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({
                        device_name: device.deviceName,
                        platform: device.platform,
                    }),
                },
            );

            const data = await response.json();

            if (!response.ok) {
                const [title, text] = friendlyError(data.detail);
                showError(title, text);
                return;
            }

            document.getElementById("result-device").textContent =
                `${data.device_name} · ${data.platform || device.platform}`;
            document.getElementById("result-location").textContent =
                `Сервер: ${data.node_name}`;

            if (data.vless_url) {
                document.getElementById("vless-url").value = data.vless_url;
                document.getElementById("configuration-block").hidden = false;
            }

            document.getElementById("activation").hidden = true;
            document.getElementById("result").hidden = false;
        } catch {
            showError(
                "Нет соединения",
                "Не удалось связаться с Work&PlayVPN. Проверьте интернет и повторите попытку.",
            );
        }
    });

    copyButton.addEventListener("click", async () => {
        const textarea = document.getElementById("vless-url");

        try {
            await navigator.clipboard.writeText(textarea.value);
            copyButton.textContent = "Скопировано";
        } catch {
            textarea.select();
            textarea.setSelectionRange(0, textarea.value.length);
        }
    });
});
