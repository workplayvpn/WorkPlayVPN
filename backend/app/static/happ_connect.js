"use strict";

const telegramApp = window.Telegram?.WebApp;
let telegramBackHandler = null;

if (telegramApp) {
    telegramApp.ready();
    telegramApp.expand();

    try {
        telegramApp.setHeaderColor("#081524");
        telegramApp.setBackgroundColor("#050b14");
    } catch {
        // Старые версии Telegram могут не поддерживать эти методы.
    }
}

function navigateBack() {
    try {
        telegramApp?.BackButton?.hide();
    } catch {
        // Older Telegram clients may not support hiding the button.
    }

    const tier = new URLSearchParams(window.location.search).get("return_tier");
    if (["basic", "mobile"].includes(tier)) {
        if (window.history.length > 1) window.history.back();
        else window.location.assign(`/app/?view=devices&detail_tier=${tier}${window.location.hash}`);
        return;
    }
    if (window.history.length > 1) {
        window.history.back();
        return;
    }

    if (telegramApp?.initData) {
        telegramApp.close();
        return;
    }

    window.location.assign("/app/");
}

function initializeBackNavigation() {
    const backButton = telegramApp?.BackButton;

    if (!backButton) {
        return;
    }

    telegramBackHandler = navigateBack;

    backButton.onClick(telegramBackHandler);
    backButton.show();
}

function removeBackNavigation() {
    if (!telegramBackHandler) {
        return;
    }

    telegramApp?.BackButton?.offClick?.(telegramBackHandler);
    telegramBackHandler = null;
}

function detectPlatform() {
    const userAgent = navigator.userAgent.toLowerCase();

    const platform = (
        navigator.userAgentData?.platform
        || navigator.platform
        || ""
    ).toLowerCase();

    if (
        /smart-tv|smarttv|appletv|googletv|android tv|hbbtv/.test(
            userAgent
        )
    ) {
        return "tv";
    }

    if (
        /iphone|ipad|ipod/.test(userAgent)
        || (
            platform === "macintel"
            && navigator.maxTouchPoints > 1
        )
    ) {
        return "ios";
    }

    if (/android/.test(userAgent)) {
        return "android";
    }

    if (/windows/.test(userAgent)) {
        return "windows";
    }

    if (/macintosh|mac os x/.test(userAgent)) {
        return "macos";
    }

    if (/linux/.test(userAgent)) {
        return "linux";
    }

    return "ios";
}

function initializePlatformSwitcher() {
    const tabs = Array.from(
        document.querySelectorAll("[data-platform]")
    );

    const panels = Array.from(
        document.querySelectorAll("[data-panel]")
    );

    if (!tabs.length || !panels.length) {
        return;
    }

    function activatePlatform(
        platform,
        scrollToPanel = false
    ) {
        const selectedTab = tabs.find(
            (tab) => tab.dataset.platform === platform
        );

        const selectedPanel = panels.find(
            (panel) => panel.dataset.panel === platform
        );

        if (!selectedTab || !selectedPanel) {
            return;
        }

        tabs.forEach((tab) => {
            const isActive = tab === selectedTab;

            tab.classList.toggle("active", isActive);

            tab.setAttribute(
                "aria-selected",
                String(isActive)
            );

            tab.tabIndex = isActive ? 0 : -1;
        });

        panels.forEach((panel) => {
            const isActive = panel === selectedPanel;

            panel.classList.toggle("active", isActive);

            panel.setAttribute(
                "aria-hidden",
                String(!isActive)
            );
        });

        if (scrollToPanel) {
            selectedPanel.scrollIntoView({
                behavior: "smooth",
                block: "start",
            });
        }
    }

    tabs.forEach((tab) => {
        tab.addEventListener("click", () => {
            activatePlatform(
                tab.dataset.platform,
                true
            );
        });

        tab.addEventListener("keydown", (event) => {
            if (
                event.key !== "ArrowRight"
                && event.key !== "ArrowLeft"
            ) {
                return;
            }

            event.preventDefault();

            const currentIndex = tabs.indexOf(tab);

            const direction = (
                event.key === "ArrowRight" ? 1 : -1
            );

            const nextIndex = (
                currentIndex
                + direction
                + tabs.length
            ) % tabs.length;

            const nextTab = tabs[nextIndex];

            activatePlatform(
                nextTab.dataset.platform
            );

            nextTab.focus();
        });
    });

    activatePlatform(detectPlatform());
}

function initializeHappLinks() {
    const links = document.querySelectorAll(
        "[data-happ-link]"
    );

    links.forEach((link) => {
        link.addEventListener("click", (event) => {
            if (telegramApp?.HapticFeedback) {
                telegramApp.HapticFeedback.impactOccurred(
                    "medium"
                );
            }

            if (!telegramApp?.openLink) {
                return;
            }

            event.preventDefault();

            const externalUrl = new URL(
                link.getAttribute("href"),
                window.location.href
            ).toString();

            telegramApp.openLink(
                externalUrl,
                {
                    try_instant_view: false,
                }
            );
        });
    });
}

document.addEventListener("DOMContentLoaded", () => {
    document.querySelector("[data-connect-back]")?.addEventListener(
        "click", navigateBack
    );
    initializeBackNavigation();
    initializePlatformSwitcher();
    initializeHappLinks();
});

window.addEventListener("pagehide", removeBackNavigation);
