document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-toggle-password]").forEach((button) => {
    button.addEventListener("click", () => {
      const input = document.getElementById(button.dataset.togglePassword);
      if (!input) return;
      const showing = input.type === "password";
      input.type = showing ? "text" : "password";
      button.setAttribute("aria-pressed", String(showing));
      button.setAttribute("aria-label", showing ? "Hide password" : "Show password");
      const icon = button.querySelector("i");
      if (icon) icon.className = showing ? "bi bi-eye-slash" : "bi bi-eye";
    });
  });

  document.querySelectorAll(".role-card").forEach((card) => {
    card.addEventListener("click", () => card.classList.add("is-selected"));
  });

  document.querySelectorAll("form[data-auth-form]").forEach((form) => {
    form.addEventListener("submit", () => {
      const button = form.querySelector('button[type="submit"]');
      if (!button || !form.reportValidity()) return;
      button.disabled = true;
      button.setAttribute("aria-busy", "true");
      button.innerHTML = `<span>${button.dataset.loadingLabel || "Please wait…"}</span><span class="auth-spinner" aria-hidden="true"></span>`;
    });
  });

  const newPassword = document.getElementById("reset-password");
  const strengthBar = document.querySelector("[data-strength-bar]");
  const strengthLabel = document.querySelector("[data-strength-label]");
  const passwordRules = [...document.querySelectorAll("[data-password-rule]")];
  const updatePasswordStrength = () => {
    if (!newPassword || !strengthBar || !strengthLabel) return;
    const checks = {
      length: newPassword.value.length >= 8,
      uppercase: /[A-Z]/.test(newPassword.value),
      lowercase: /[a-z]/.test(newPassword.value),
      number: /\d/.test(newPassword.value),
      special: /[^A-Za-z0-9]/.test(newPassword.value),
    };
    const score = Object.values(checks).filter(Boolean).length;
    strengthBar.style.width = `${score * 20}%`;
    strengthBar.dataset.score = String(score);
    strengthLabel.textContent = score === 0 ? "Enter a password" : score < 3 ? "Weak" : score < 5 ? "Almost there" : "Strong password";
    passwordRules.forEach((rule) => {
      const passed = checks[rule.dataset.passwordRule];
      rule.classList.toggle("is-valid", passed);
      rule.setAttribute("aria-label", `${passed ? "Met" : "Not met"}: ${rule.textContent}`);
    });
  };
  newPassword?.addEventListener("input", updatePasswordStrength);
  updatePasswordStrength();

  const drawer = document.getElementById("side-drawer");
  const menuTrigger = document.getElementById("menu-trigger");
  const scrim = document.getElementById("drawer-scrim");
  const closeButton = document.querySelector("[data-close-drawer]");
  let previousFocus = null;

  const focusableIn = (element) =>
    [...element.querySelectorAll('a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])')]
      .filter((item) => item.getAttribute("aria-hidden") !== "true");

  const closeDrawer = () => {
    if (!drawer?.classList.contains("is-open")) return;
    drawer.classList.remove("is-open");
    document.body.classList.remove("drawer-open");
    scrim?.classList.remove("is-visible");
    drawer.setAttribute("aria-hidden", "true");
    menuTrigger?.setAttribute("aria-expanded", "false");
    menuTrigger?.setAttribute("aria-label", "Open navigation menu");
    window.setTimeout(() => {
      if (!drawer.classList.contains("is-open") && scrim) scrim.hidden = true;
    }, 240);
    (previousFocus || menuTrigger)?.focus();
  };

  const openDrawer = () => {
    if (!drawer) return;
    previousFocus = document.activeElement;
    drawer.setAttribute("aria-hidden", "false");
    scrim.hidden = false;
    menuTrigger?.setAttribute("aria-expanded", "true");
    menuTrigger?.setAttribute("aria-label", "Close navigation menu");
    requestAnimationFrame(() => {
      scrim.classList.add("is-visible");
      drawer.classList.add("is-open");
      document.body.classList.add("drawer-open");
      closeButton?.focus();
    });
  };

  menuTrigger?.addEventListener("click", () => {
    drawer.classList.contains("is-open") ? closeDrawer() : openDrawer();
  });
  closeButton?.addEventListener("click", closeDrawer);
  scrim?.addEventListener("click", closeDrawer);
  drawer?.querySelectorAll("a[href]").forEach((link) => link.addEventListener("click", closeDrawer));

  document.addEventListener("keydown", (event) => {
    if (!drawer?.classList.contains("is-open")) return;
    if (event.key === "Escape") {
      event.preventDefault();
      closeDrawer();
      return;
    }
    if (event.key !== "Tab") return;
    const focusable = focusableIn(drawer);
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (!drawer.contains(document.activeElement)) {
      event.preventDefault();
      first.focus();
      return;
    }
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  });

  let touchStartX = null;
  drawer?.addEventListener("touchstart", (event) => {
    touchStartX = event.changedTouches[0]?.clientX ?? null;
  }, { passive: true });
  drawer?.addEventListener("touchend", (event) => {
    const touchEndX = event.changedTouches[0]?.clientX;
    if (touchStartX !== null && touchEndX !== undefined && touchStartX - touchEndX > 65) closeDrawer();
    touchStartX = null;
  }, { passive: true });

  const root = document.documentElement;
  const themeToggle = document.querySelector("[data-theme-toggle]");
  const setTheme = (theme) => {
    const dark = theme === "dark";
    root.dataset.theme = dark ? "dark" : "light";
    themeToggle?.setAttribute("aria-pressed", String(dark));
    const label = themeToggle?.querySelector("span:nth-child(2)");
    if (label) label.textContent = dark ? "Light appearance" : "Dark appearance";
    const icon = themeToggle?.querySelector("i");
    if (icon) icon.className = dark ? "bi bi-sun" : "bi bi-moon-stars";
  };
  try {
    setTheme(window.localStorage.getItem("proguide-theme") || "light");
  } catch {
    setTheme("light");
  }
  themeToggle?.addEventListener("click", () => {
    const next = root.dataset.theme === "dark" ? "light" : "dark";
    setTheme(next);
    try {
      window.localStorage.setItem("proguide-theme", next);
    } catch {
      // Theme still changes for this page if storage is unavailable.
    }
  });

  document.querySelectorAll(".toast-dismiss").forEach((button) => {
    button.addEventListener("click", () => button.closest(".toast-message")?.remove());
  });
  document.querySelectorAll(".toast-message").forEach((toast) => {
    window.setTimeout(() => toast.remove(), 7000);
  });

  document.querySelectorAll("[data-count]").forEach((counter) => {
    const target = Number.parseInt(counter.dataset.count || "0", 10);
    if (!Number.isFinite(target) || target <= 0 || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const duration = 500;
    const start = performance.now();
    const update = (now) => {
      const progress = Math.min(1, (now - start) / duration);
      counter.textContent = String(Math.round(target * (1 - (1 - progress) ** 3)));
      if (progress < 1) requestAnimationFrame(update);
    };
    requestAnimationFrame(update);
  });

  document.querySelectorAll(".mentor-meeting-form").forEach((form) => {
    const audience = form.querySelector("[data-meeting-audience]");
    const picker = form.querySelector("[data-meeting-mentee-picker]");
    const menteeCheckboxes = [...form.querySelectorAll('input[name="mentee_ids"]')];
    const count = form.querySelector("[data-meeting-selection-count]");
    const selectionError = form.querySelector("[data-meeting-selection-error]");
    const submit = form.querySelector("[data-meeting-submit]");
    const updateAudience = () => {
      const selecting = audience.value === "selected";
      picker.hidden = !selecting;
      const selectedCount = menteeCheckboxes.filter((checkbox) => checkbox.checked).length;
      count.textContent = selecting ? `${selectedCount} mentee${selectedCount === 1 ? "" : "s"} selected` : "";
      if (submit) {
        submit.textContent = selecting && selectedCount
          ? `Create meeting for ${selectedCount} mentee${selectedCount === 1 ? "" : "s"}`
          : "Create meeting";
      }
      menteeCheckboxes.forEach((checkbox) => {
        checkbox.closest(".meeting-mentee-option")?.classList.toggle("is-selected", checkbox.checked);
      });
      selectionError.hidden = true;
      menteeCheckboxes.forEach((checkbox) => {
        checkbox.setAttribute("aria-invalid", "false");
      });
    };
    audience?.addEventListener("change", updateAudience);
    menteeCheckboxes.forEach((checkbox) => checkbox.addEventListener("change", updateAudience));
    form.addEventListener("submit", (event) => {
      if (audience.value !== "selected" || menteeCheckboxes.some((checkbox) => checkbox.checked)) return;
      event.preventDefault();
      selectionError.hidden = false;
      menteeCheckboxes.forEach((checkbox) => checkbox.setAttribute("aria-invalid", "true"));
      menteeCheckboxes[0]?.focus();
    });
    updateAudience();
  });

  const chatApp = document.getElementById("chat-app");
  const chatMessages = document.getElementById("chat-messages");
  const chatForm = document.getElementById("chat-form");
  if (chatApp && chatMessages && chatForm) {
    const chatKind = chatApp.dataset.selectedKind || "direct";
    const recipientId = chatApp.dataset.selectedRecipient;
    const groupId = chatApp.dataset.selectedGroup;
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || "";
    const chatError = document.getElementById("chat-error");
    const contentInput = document.getElementById("chat-content");
    const emergencyInput = chatForm.querySelector('input[name="emergency"]');
    const count = document.getElementById("chat-char-count");
    const sendButton = document.getElementById("chat-send");
    const seenSent = new Set();
    let requestInProgress = false;
    const threadUrl = chatKind === "group"
      ? `/messages/api/group/${encodeURIComponent(groupId)}`
      : `/messages/api/thread/${encodeURIComponent(recipientId)}`;
    const setChatError = (message = "") => {
      chatError.textContent = message;
      chatError.hidden = !message;
    };
    const setRecipient = (recipient) => {
      document.getElementById("chat-recipient-name").textContent = recipient.name;
      const avatar = document.getElementById("chat-avatar");
      if (avatar) avatar.textContent = recipient.name.slice(0, 1).toLocaleUpperCase();
    };
    const setGroup = (group) => {
      document.getElementById("chat-recipient-name").textContent = group.name;
      const members = document.getElementById("chat-group-members");
      if (members) members.textContent = `${group.members.length} members · ${group.members.join(", ")}`;
    };
    const addMessage = (message, shouldScroll) => {
      let row = chatMessages.querySelector(`[data-message-id="${message.id}"]`);
      const isNew = !row;
      if (isNew) {
        row = document.createElement("article");
        row.className = `chat-message ${message.is_mine ? "chat-message-mine" : "chat-message-theirs"}`;
        row.dataset.messageId = String(message.id);
        const bubble = document.createElement("div");
        bubble.className = "chat-bubble";
        if (chatKind === "group" && !message.is_mine) {
          const sender = document.createElement("strong");
          sender.className = "chat-group-sender";
          sender.textContent = message.sender_name;
          bubble.append(sender);
        }
        const text = document.createElement("p");
        text.className = "chat-message-content";
        text.textContent = message.content;
        bubble.append(text);
        const meta = document.createElement("div");
        meta.className = "chat-message-meta";
        const time = document.createElement("time");
        time.dateTime = message.created_at;
        time.textContent = new Date(message.created_at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
        meta.append(time);
        if (message.is_mine && chatKind !== "group") {
          const status = document.createElement("span");
          status.className = "chat-message-status";
          status.dataset.messageStatus = "";
          meta.append(status);
        }
        bubble.append(meta);
        row.append(bubble);
        chatMessages.append(row);
      }
      if (message.is_mine && chatKind !== "group") {
        const status = row.querySelector("[data-message-status]");
        const seen = message.is_read;
        const delivered = message.delivered;
        status.textContent = seen || delivered ? "\u2713\u2713" : "\u2713";
        status.classList.toggle("is-received", delivered && !seen);
        status.classList.toggle("is-seen", seen);
        status.setAttribute("aria-label", seen ? "Seen" : delivered ? "Received" : "Sent");
        status.title = seen ? "Seen" : delivered ? "Received" : "Sent";
      }
      if (shouldScroll && isNew) chatMessages.scrollTop = chatMessages.scrollHeight;
      return isNew;
    };
    const loadThread = async () => {
      if (requestInProgress || document.hidden) return;
      requestInProgress = true;
      try {
        const response = await fetch(threadUrl, { headers: { Accept: "application/json" } });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Could not load this conversation.");
        setChatError("");
        if (chatKind === "group") setGroup(data.group);
        else setRecipient(data.recipient);
        const wasAtBottom = chatMessages.scrollHeight - chatMessages.scrollTop - chatMessages.clientHeight < 80;
        let addedMessages = false;
        const newlySeenIds = [];
        data.messages.forEach((message) => {
          const isNew = addMessage(message, false);
          addedMessages = addedMessages || isNew;
          if (chatKind !== "group" && !message.is_mine && !message.is_read && !seenSent.has(message.id)) {
            newlySeenIds.push(message.id);
          }
        });
        if (!data.messages.length && !chatMessages.querySelector(".chat-message")) {
          chatMessages.innerHTML = '<div class="chat-empty-thread"><span class="empty-illustration"><i class="bi bi-chat-heart" aria-hidden="true"></i></span><strong>No messages yet</strong><p>Send a message to begin the conversation.</p></div>';
        } else {
          chatMessages.querySelector(".chat-loading, .chat-empty-thread")?.remove();
        }
        if (addedMessages && wasAtBottom) chatMessages.scrollTop = chatMessages.scrollHeight;
        if (chatKind !== "group" && newlySeenIds.length) {
          const seenResponse = await fetch(`${threadUrl}/seen`, {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken, Accept: "application/json" },
            body: JSON.stringify({ message_ids: newlySeenIds }),
          });
          if (!seenResponse.ok) throw new Error("Messages loaded, but read receipts could not be updated.");
          newlySeenIds.forEach((messageId) => seenSent.add(messageId));
        }
      } catch (error) {
        setChatError(error.message || "Chat could not be updated. Please retry.");
      } finally {
        requestInProgress = false;
      }
    };
    contentInput?.addEventListener("input", () => {
      if (count) count.textContent = String(contentInput.value.length);
      contentInput.style.height = "auto";
      contentInput.style.height = `${Math.min(contentInput.scrollHeight, 120)}px`;
    });
    chatForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!contentInput.value.trim()) {
        contentInput.focus();
        setChatError("Write a message before sending.");
        return;
      }
      sendButton.disabled = true;
      sendButton.setAttribute("aria-busy", "true");
      try {
        const response = await fetch(threadUrl, {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken, Accept: "application/json" },
          body: JSON.stringify({
            content: contentInput.value,
            ...(chatKind === "group" ? {} : { emergency: Boolean(emergencyInput?.checked) }),
          }),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Message could not be sent.");
        contentInput.value = "";
        contentInput.style.height = "auto";
        if (count) count.textContent = "0";
        if (emergencyInput) emergencyInput.checked = false;
        setChatError("");
        chatMessages.querySelector(".chat-empty-thread, .chat-loading")?.remove();
        addMessage(data, true);
        contentInput.focus();
      } catch (error) {
        setChatError(error.message || "Message could not be sent. Please try again.");
      } finally {
        sendButton.disabled = false;
        sendButton.removeAttribute("aria-busy");
      }
    });
    loadThread();
    window.setInterval(loadThread, 3000);
  }

  const chartCanvas = document.querySelector("[data-dashboard-chart]");
  if (chartCanvas && window.Chart) {
    try {
      const labels = JSON.parse(chartCanvas.dataset.labels || "[]");
      const users = JSON.parse(chartCanvas.dataset.users || "[]");
      const meetings = JSON.parse(chartCanvas.dataset.meetings || "[]");
      new Chart(chartCanvas, {
        type: "line",
        data: {
          labels,
          datasets: [
            { label: "New users", data: users, borderColor: "#2563eb", backgroundColor: "rgb(37 99 235 / 10%)", fill: true, tension: 0.35 },
            { label: "Sessions", data: meetings, borderColor: "#14b8a6", backgroundColor: "rgb(20 184 166 / 8%)", fill: true, tension: 0.35 },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: { intersect: false, mode: "index" },
          plugins: { legend: { display: false }, tooltip: { enabled: true } },
          scales: {
            x: { grid: { display: false }, ticks: { color: "#64748b" } },
            y: { beginAtZero: true, ticks: { precision: 0, color: "#64748b" }, grid: { color: "rgb(148 163 184 / 16%)" } },
          },
        },
      });
    } catch (error) {
      console.error("Unable to render the dashboard chart.", error);
    }
  }

  const notificationButton = document.getElementById("notification-trigger");
  const notificationPanel = document.getElementById("notification-panel");
  const notificationList = document.querySelector("[data-notification-list]");
  const unreadBadge = document.querySelector("[data-unread-count]");
  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || "";
  let notificationRequest = null;

  const loadNotifications = async () => {
    if (!notificationList) return Promise.resolve();
    if (notificationRequest) return notificationRequest;
    notificationRequest = (async () => {
      try {
        const response = await fetch("/api/notifications", {
          headers: { Accept: "application/json" },
          cache: "no-store",
        });
        if (!response.ok) throw new Error(`Notifications request failed (${response.status}).`);
        const notifications = await response.json();
        const unreadCountHeader = response.headers.get("X-Unread-Count");
        const unreadCount = unreadCountHeader === null ? Number.NaN : Number(unreadCountHeader);
        const displayedCount = Number.isFinite(unreadCount) ? unreadCount : notifications.length;
        if (unreadBadge) {
          unreadBadge.textContent = String(displayedCount);
          unreadBadge.classList.toggle("is-hidden", displayedCount === 0);
        }
        notificationList.replaceChildren();
        if (!notifications.length) {
          const empty = document.createElement("p");
          empty.className = "empty-copy";
          empty.textContent = "You’re all caught up.";
          notificationList.append(empty);
          return;
        }
        notifications.forEach((notification) => {
          const item = document.createElement("article");
          item.className = "notification-item";
          const dot = document.createElement("span");
          dot.className = "notification-dot";
          const text = document.createElement("p");
          text.textContent = notification.message;
          if (notification.url) {
            const view = document.createElement("a");
            view.className = "text-button";
            view.href = notification.url;
            view.textContent = "View achievements";
            item.append(dot, text, view);
          } else {
            item.append(dot, text);
          }
          const markRead = document.createElement("button");
          markRead.className = "text-button";
          markRead.type = "button";
          markRead.textContent = "Mark read";
          markRead.setAttribute("aria-label", `Mark notification read: ${notification.message}`);
          markRead.addEventListener("click", async () => {
            try {
              const result = await fetch(`/api/notifications/${notification.id}/read`, {
                method: "POST",
                headers: { "X-CSRFToken": csrfToken, Accept: "application/json" },
              });
              if (!result.ok) throw new Error(`Could not mark notification read (${result.status}).`);
              await loadNotifications();
            } catch {
              const errorMessage = document.createElement("p");
              errorMessage.className = "empty-copy";
              errorMessage.setAttribute("role", "status");
              errorMessage.textContent = "This notification could not be updated. Please refresh and try again.";
              notificationList.prepend(errorMessage);
            }
          });
          item.append(markRead);
          notificationList.append(item);
        });
      } catch {
        if (notificationPanel && !notificationPanel.hidden) {
          notificationList.replaceChildren();
          const message = document.createElement("p");
          message.className = "empty-copy";
          message.setAttribute("role", "status");
          message.textContent = "Notifications could not be loaded. Please try again.";
          notificationList.append(message);
        }
      } finally {
        notificationRequest = null;
      }
    })();
    return notificationRequest;
  };

  notificationButton?.addEventListener("click", () => {
    const opening = notificationPanel.hidden;
    notificationPanel.hidden = !opening;
    notificationButton.setAttribute("aria-expanded", String(opening));
    if (opening) loadNotifications();
  });
  document.querySelector("[data-refresh-notifications]")?.addEventListener("click", loadNotifications);
  document.addEventListener("click", (event) => {
    if (!notificationPanel || notificationPanel.hidden) return;
    if (!notificationPanel.contains(event.target) && !notificationButton.contains(event.target)) {
      notificationPanel.hidden = true;
      notificationButton.setAttribute("aria-expanded", "false");
    }
  });
  if (notificationList) {
    window.setInterval(() => {
      if (!document.hidden) loadNotifications();
    }, 60000);
  }
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && notificationPanel && !notificationPanel.hidden) {
      notificationPanel.hidden = true;
      notificationButton?.setAttribute("aria-expanded", "false");
    }
  });

  const onboardingDialog = document.getElementById("onboarding-dialog");
  if (onboardingDialog && document.body.dataset.onboardingDashboard === "true") {
    const tourKey = `proguide-tour-${document.body.dataset.onboardingUser}`;
    let completed = false;
    try {
      completed = window.localStorage.getItem(tourKey) === "done";
    } catch {
      completed = true;
    }
    if (!completed) onboardingDialog.showModal();

    let tourStep = 0;
    const steps = [...onboardingDialog.querySelectorAll("[data-tour-step]")];
    const progress = onboardingDialog.querySelector("[data-tour-progress]");
    const finishTour = () => {
      onboardingDialog.close();
      try {
        window.localStorage.setItem(tourKey, "done");
      } catch {
        // The tour can still be dismissed when storage is unavailable.
      }
    };
    onboardingDialog.querySelectorAll("[data-tour-skip]").forEach((button) => button.addEventListener("click", finishTour));
    onboardingDialog.querySelector("[data-tour-next]")?.addEventListener("click", () => {
      if (tourStep >= steps.length - 1) {
        finishTour();
        return;
      }
      steps[tourStep].hidden = true;
      tourStep += 1;
      steps[tourStep].hidden = false;
      if (progress) progress.style.width = `${((tourStep + 1) / steps.length) * 100}%`;
      const nextButton = onboardingDialog.querySelector("[data-tour-next]");
      if (nextButton) nextButton.textContent = tourStep === steps.length - 1 ? "Finish" : "Next";
    });
    onboardingDialog.addEventListener("cancel", () => {
      try {
        window.localStorage.setItem(tourKey, "done");
      } catch {
        // Dismissing with Escape still completes the tour.
      }
    });
  }

  const commandDialog = document.getElementById("command-dialog");
  const commandInput = document.getElementById("command-input");
  const commandResults = document.getElementById("command-results");
  const pageResults = [...(commandResults?.querySelectorAll(".command-result") || [])];
  let personResults = [];
  let searchTimer;

  const openSearch = () => {
    if (!commandDialog || commandDialog.open) return;
    commandDialog.showModal();
    commandInput.value = "";
    pageResults.forEach((item) => { item.hidden = false; });
    personResults.forEach((item) => item.remove());
    personResults = [];
    commandInput.focus();
  };
  document.querySelectorAll("[data-open-search]").forEach((button) => button.addEventListener("click", openSearch));
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && commandDialog?.open) {
      event.preventDefault();
      commandDialog.close();
      return;
    }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      openSearch();
    }
  });
  commandDialog?.addEventListener("click", (event) => {
    if (event.target === commandDialog) commandDialog.close();
  });
  commandInput?.addEventListener("input", () => {
    const query = commandInput.value.trim();
    const normalizedQuery = query.toLocaleLowerCase();
    pageResults.forEach((item) => {
      item.hidden = !item.textContent.toLocaleLowerCase().includes(normalizedQuery);
    });
    personResults.forEach((item) => item.remove());
    personResults = [];
    window.clearTimeout(searchTimer);
    if (query.length < 2) return;
    searchTimer = window.setTimeout(async () => {
      try {
        const response = await fetch(`/api/search?q=${encodeURIComponent(query)}`, { headers: { Accept: "application/json" } });
        if (!response.ok) throw new Error(`People search failed (${response.status}).`);
        const people = await response.json();
        people.forEach((person) => {
          const result = document.createElement("a");
          result.className = "command-result";
          result.href = person.url;
          result.dataset.personResult = "";
          result.setAttribute("role", "option");
          const icon = document.createElement("i");
          icon.className = "bi bi-person";
          icon.setAttribute("aria-hidden", "true");
          const name = document.createElement("span");
          name.textContent = person.name;
          const role = document.createElement("small");
          role.textContent = person.role;
          result.append(icon, name, role);
          result.addEventListener("click", () => commandDialog.close());
          commandResults.append(result);
          personResults.push(result);
        });
      } catch (error) {
        console.error(error);
      }
    }, 180);
  });
  commandResults?.addEventListener("click", (event) => {
    if (event.target.closest("a.command-result")) commandDialog.close();
  });

  document.querySelectorAll("form[data-confirm-reject]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      const decision = form.querySelector('select[name="decision"]')?.value;
      if (decision === "Rejected" && !window.confirm("Reject this session request? The mentee will be notified.")) {
        event.preventDefault();
      }
    });
  });

  document.querySelectorAll("form[data-confirm-delete]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      const accountName = form.dataset.confirmDelete;
      const confirmed = window.confirm(
        `Permanently delete ${accountName} and their related records? This action cannot be undone.`,
      );
      if (!confirmed) event.preventDefault();
    });
  });
});
