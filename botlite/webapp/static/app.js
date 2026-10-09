const tg = globalThis.Telegram?.WebApp;
if (tg) {
  tg.expand();
  tg.ready();
}
const initData = tg?.initData || "";

let toastTimer;
function toast(message, duration = 2800) {
  const element = document.getElementById("toast");
  element.textContent = message;
  element.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => element.classList.remove("show"), duration);
}

function setText(id, value) {
  document.getElementById(id).textContent = String(value);
}

function setBadge(id, className, content) {
  const wrapper = document.getElementById(id);
  const badge = document.createElement("span");
  badge.className = `badge ${className}`;
  badge.textContent = String(content);
  wrapper.replaceChildren(badge);
}

try {
  const response = await fetch("/api/status");
  if (!response.ok) { throw new Error(String(response.status)); }
  const status = await response.json();

  setText("ver", `v${status.version}`);
  setText("uptime", status.uptime);
  setText("max-dl", status.max_concurrent);

  const activeClass = status.active_downloads > 0 ? "badge-orange" : "badge-green";
  setBadge("active", activeClass, `${status.active_downloads} / ${status.max_concurrent}`);

  const bytes = status.free_disk_bytes;
  let diskClass = "badge-green";
  let barClass = "";
  if (bytes < 500 * 1024 * 1024) {
    diskClass = "badge-red";
    barClass = "crit";
  } else if (bytes < 2 * 1024 * 1024 * 1024) {
    diskClass = "badge-orange";
    barClass = "warn";
  }
  setBadge("disk", diskClass, status.free_disk);

  const referenceBytes = 50 * 1024 * 1024 * 1024;
  const percentage = Math.min(100, Math.round((bytes / referenceBytes) * 100));
  const bar = document.getElementById("disk-bar");
  bar.style.width = `${percentage}%`;
  if (barClass) { bar.classList.add(barClass); }
  document.getElementById("disk-bar-wrap").classList.remove("hidden");
} catch {
  toast("⚠️ Could not load status");
}

if (initData) {
  try {
    const response = await fetch("/api/stats", {
      headers: { "X-Telegram-Init-Data": initData },
    });
    if (response.ok) {
      const stats = await response.json();
      document.getElementById("admin-section").style.display = "block";
      setText("total-dl", stats.total_downloads);
      setText("failed-dl", stats.failed_downloads);

      const total = stats.total_downloads + stats.failed_downloads;
      const rate = total ? Math.round((stats.total_downloads / total) * 100) : 100;
      const fallbackClass = rate >= 70 ? "badge-orange" : "badge-red";
      const rateClass = rate >= 90 ? "badge-green" : fallbackClass;
      setBadge("success-rate", rateClass, `${rate}%`);
    }
  } catch {
    // Authenticated statistics are optional; keep the admin section hidden.
  }
}

async function doAction(action) {
  const rawUserId = document.getElementById("ban-uid").value.trim();
  if (!rawUserId) { toast("Enter a Telegram User ID"); return; }
  const userId = Number.parseInt(rawUserId, 10);
  if (!userId) { toast("Invalid User ID"); return; }

  try {
    const response = await fetch(`/api/${action}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Telegram-Init-Data": initData,
      },
      body: JSON.stringify({ user_id: userId }),
    });
    if (response.ok) {
      toast(action === "ban" ? `🚫 User ${userId} banned` : `✅ User ${userId} unbanned`);
      document.getElementById("ban-uid").value = "";
    } else {
      toast(`❌ ${response.status === 403 ? "Not authorized" : "Failed"}`);
    }
  } catch {
    toast("❌ Network error");
  }
}

document.getElementById("btn-ban").addEventListener("click", () => doAction("ban"));
document.getElementById("btn-unban").addEventListener("click", () => doAction("unban"));
