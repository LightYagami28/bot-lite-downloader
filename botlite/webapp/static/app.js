/* global document, fetch, setTimeout, clearTimeout, window */
(function () {
  "use strict";

  var TOAST_MS = 2800;
  var MB = 1024 * 1024;
  var CRITICAL_BYTES = 500 * MB;
  var WARNING_BYTES = 2048 * MB;
  var REFERENCE_BYTES = 51200 * MB;
  var PERCENT = 100;
  var GOOD_RATE = 90;
  var FAIR_RATE = 70;
  var DECIMAL = 10;
  var FORBIDDEN = 403;
  var telegram = window.Telegram && window.Telegram.WebApp;
  var initData = (telegram && telegram.initData) || "";
  var toastTimer;

  if (telegram) {
    telegram.expand();
    telegram.ready();
  }

  function byId(id) {
    return document.getElementById(id);
  }

  function toast(message) {
    var element = byId("toast");
    element.textContent = message;
    element.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () {
      element.classList.remove("show");
    }, TOAST_MS);
  }

  function setText(id, value) {
    byId(id).textContent = String(value);
  }

  function setBadge(id, className, content) {
    var badge = document.createElement("span");
    badge.className = "badge " + className;
    badge.textContent = String(content);
    byId(id).replaceChildren(badge);
  }

  function diskLevel(bytes) {
    if (bytes < CRITICAL_BYTES) {
      return { badge: "badge-red", bar: "crit" };
    }
    if (bytes < WARNING_BYTES) {
      return { badge: "badge-orange", bar: "warn" };
    }
    return { badge: "badge-green", bar: "" };
  }

  function showDisk(status) {
    var level = diskLevel(status.free_disk_bytes);
    var bar = byId("disk-bar");
    var percentage = Math.min(PERCENT, Math.round((status.free_disk_bytes / REFERENCE_BYTES) * PERCENT));
    setBadge("disk", level.badge, status.free_disk);
    bar.style.width = percentage + "%";
    if (level.bar) {
      bar.classList.add(level.bar);
    }
    byId("disk-bar-wrap").classList.remove("hidden");
  }

  function showStatus(status) {
    var active = status.active_downloads > 0 ? "badge-orange" : "badge-green";
    setText("ver", "v" + status.version);
    setText("uptime", status.uptime);
    setText("max-dl", status.max_concurrent);
    setBadge("active", active, status.active_downloads + " / " + status.max_concurrent);
    showDisk(status);
  }

  function rateClass(rate) {
    if (rate >= GOOD_RATE) {
      return "badge-green";
    }
    return rate >= FAIR_RATE ? "badge-orange" : "badge-red";
  }

  function showStats(stats) {
    var total = stats.total_downloads + stats.failed_downloads;
    var rate = total ? Math.round((stats.total_downloads / total) * PERCENT) : PERCENT;
    byId("admin-section").style.display = "block";
    setText("total-dl", stats.total_downloads);
    setText("failed-dl", stats.failed_downloads);
    setBadge("success-rate", rateClass(rate), rate + "%");
  }

  function loadStats() {
    if (!initData) {
      return Promise.resolve();
    }
    return fetch("/api/stats", { headers: { "X-Telegram-Init-Data": initData } })
      .then(function (response) {
        return response.ok ? response.json().then(showStats) : null;
      })
      .catch(function () {
        return null;
      });
  }

  function loadStatus() {
    return fetch("/api/status")
      .then(function (response) {
        if (!response.ok) {
          throw new Error(String(response.status));
        }
        return response.json();
      })
      .then(showStatus)
      .catch(function () {
        toast("⚠️ Could not load status");
      })
      .then(loadStats);
  }

  function actionMessage(action, userId) {
    return action === "ban" ? "🚫 User " + userId + " banned" : "✅ User " + userId + " unbanned";
  }

  function failureMessage(response) {
    return "❌ " + (response.status === FORBIDDEN ? "Not authorized" : "Failed");
  }

  function sendAction(action, userId) {
    return fetch("/api/" + action, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Telegram-Init-Data": initData },
      body: JSON.stringify({ user_id: userId })
    }).then(function (response) {
      if (response.ok) {
        toast(actionMessage(action, userId));
        byId("ban-uid").value = "";
      } else {
        toast(failureMessage(response));
      }
    });
  }

  function doAction(action) {
    var rawUserId = byId("ban-uid").value.trim();
    var userId = Number.parseInt(rawUserId, DECIMAL);
    if (!rawUserId) {
      toast("Enter a Telegram User ID");
      return Promise.resolve();
    }
    if (!userId) {
      toast("Invalid User ID");
      return Promise.resolve();
    }
    return sendAction(action, userId).catch(function () {
      toast("❌ Network error");
    });
  }

  byId("btn-ban").addEventListener("click", function () {
    return doAction("ban");
  });
  byId("btn-unban").addEventListener("click", function () {
    return doAction("unban");
  });

  loadStatus();
})();
