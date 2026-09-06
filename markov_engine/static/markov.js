(() => {
  "use strict";

  const on = (element, event, handler) => element?.addEventListener(event, handler);
  const all = (selector, root = document) => [...root.querySelectorAll(selector)];

  const activateTab = (tabs, selected, panelSelector, value) => {
    tabs.forEach((tab) => {
      const active = tab === selected;
      tab.setAttribute("aria-selected", String(active));
      tab.tabIndex = active ? 0 : -1;
    });
    if (panelSelector) {
      all(panelSelector).forEach((panel) => {
        panel.hidden = panel.dataset.caseView !== value;
      });
    }
  };

  const bindArrowTabs = (tabs, activate) => {
    tabs.forEach((tab, index) => {
      on(tab, "keydown", (event) => {
        const horizontal = ["ArrowLeft", "ArrowRight", "Home", "End"];
        const vertical = ["ArrowUp", "ArrowDown"];
        if (![...horizontal, ...vertical].includes(event.key)) return;
        event.preventDefault();
        let next = index;
        if (["ArrowRight", "ArrowDown"].includes(event.key)) next = (index + 1) % tabs.length;
        if (["ArrowLeft", "ArrowUp"].includes(event.key)) next = (index - 1 + tabs.length) % tabs.length;
        if (event.key === "Home") next = 0;
        if (event.key === "End") next = tabs.length - 1;
        tabs[next].focus();
        activate(tabs[next]);
      });
    });
  };

  const navToggle = document.querySelector("[data-nav-toggle]");
  const siteNav = document.querySelector("[data-site-nav]");
  const setPublicNav = (open) => {
    if (!navToggle || !siteNav) return;
    const wasOpen = navToggle.getAttribute("aria-expanded") === "true";
    navToggle.setAttribute("aria-expanded", String(open));
    siteNav.dataset.open = String(open);
    if (!open && wasOpen && siteNav.contains(document.activeElement)) navToggle.focus();
  };
  on(navToggle, "click", () => setPublicNav(navToggle.getAttribute("aria-expanded") !== "true"));
  all("[data-site-nav] a").forEach((link) => on(link, "click", () => setPublicNav(false)));

  const appSidebar = document.querySelector("[data-app-sidebar]");
  const appScrim = document.querySelector("[data-app-scrim]");
  const appOpen = document.querySelector("[data-app-nav-open]");
  const appClose = document.querySelector("[data-app-nav-close]");
  const mobileNav = matchMedia("(max-width: 900px)");
  const appMain = document.querySelector(".mk-app-main");
  const setAppNav = (open) => {
    if (!appSidebar || !appScrim) return;
    const wasOpen = appSidebar.dataset.open === "true";
    open = open && mobileNav.matches;
    appSidebar.dataset.open = String(open);
    appSidebar.inert = mobileNav.matches && !open;
    appScrim.hidden = !open;
    if (appMain) appMain.inert = open;
    appOpen?.setAttribute("aria-expanded", String(open));
    if (open) appClose?.focus();
    else if (wasOpen && mobileNav.matches) appOpen?.focus();
  };
  setAppNav(false);
  on(mobileNav, "change", () => setAppNav(false));
  on(appOpen, "click", () => setAppNav(true));
  on(appClose, "click", () => setAppNav(false));
  on(appScrim, "click", () => setAppNav(false));
  on(appSidebar, "keydown", (event) => {
    if (event.key !== "Tab" || !mobileNav.matches || appSidebar.dataset.open !== "true") return;
    const stops = all('a[href], button:not([disabled])', appSidebar);
    const first = stops[0], last = stops.at(-1);
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  });

  const caseTabs = all("[data-case-view-tab]");
  const documentForm = document.querySelector('#mk-document-form');
  if (documentForm) {
    const saveState = document.querySelector('[data-document-save-state]');
    let dirty = false;
    on(documentForm, 'input', () => {
      dirty = true;
      if (saveState) saveState.textContent = 'Unsaved changes';
    });
    on(documentForm, 'submit', () => {
      dirty = false;
      if (saveState) saveState.textContent = 'Saving revision…';
    });
    on(window, 'beforeunload', event => {
      if (!dirty) return;
      event.preventDefault();
      event.returnValue = '';
    });
    on(window, 'pageshow', () => {
      if (saveState) saveState.textContent = dirty ? 'Unsaved changes' : 'Saved version';
    });
  }
  const caseViewAlias = { brief: "output", landscape: "explore", opportunity: "explore" };
  const chooseCaseView = (tab, updateHash = true) => {
    const value = tab.dataset.caseViewTab;
    activateTab(caseTabs, tab, "[data-case-view]", value);
    if (updateHash) history.replaceState(null, "", `#${value}`);
  };
  caseTabs.forEach((tab) => on(tab, "click", () => chooseCaseView(tab)));
  if (caseTabs.length) {
    bindArrowTabs(caseTabs, chooseCaseView);
    const requested = location.hash.slice(1);
    const initial = caseViewAlias[requested] || requested;
    const initialTab = caseTabs.find((tab) => tab.dataset.caseViewTab === initial);
    if (initialTab) chooseCaseView(initialTab, false);
  }
  all("[data-case-view-jump]").forEach((button) => {
    on(button, "click", () => {
      const target = button.dataset.caseViewJump;
      const tab = caseTabs.find((item) => item.dataset.caseViewTab === target);
      if (tab) {
        chooseCaseView(tab);
        tab.focus();
        window.scrollTo({ top: 0, behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
      }
    });
  });

  all("[data-route-toggle]").forEach((button) => {
    on(button, "click", () => {
      const card = button.closest("[data-route-card]");
      const panel = card?.querySelector("[data-route-panel]");
      const open = button.getAttribute("aria-expanded") !== "true";
      button.setAttribute("aria-expanded", String(open));
      if (panel) panel.hidden = !open;
      card?.classList.toggle("is-open", open);
    });
  });

  all("[data-reject-opportunity]").forEach((button) => {
    on(button, "click", () => {
      const card = button.closest("[data-route-card]") || button.parentElement;
      const form = card?.querySelector("[data-rejection-reason]");
      if (!form) return;
      form.hidden = false;
      form.querySelector("input")?.focus();
    });
  });

  const composer = document.querySelector("[data-output-composer]");
  let composerTrigger = null;
  const closeComposer = () => {
    if (!composer?.open) return;
    composer.close();
    composerTrigger?.focus();
  };
  all("[data-open-composer]").forEach((button) => {
    on(button, "click", () => {
      if (!composer) return;
      composerTrigger = button;
      const topic = composer.querySelector("[data-composer-topic]");
      const angle = composer.querySelector("[data-composer-angle]");
      const context = composer.querySelector("[data-composer-context]");
      if (topic) topic.value = button.dataset.topicId || "";
      if (angle) angle.value = button.dataset.topicFocus || "";
      if (context) context.textContent = `Working from “${button.dataset.topicTitle || "this angle"}”.`;
      composer.showModal();
      requestAnimationFrame(() => angle?.focus());
    });
  });
  all("[data-close-composer]").forEach((button) => on(button, "click", closeComposer));
  on(composer, "click", (event) => {
    const bounds = composer.getBoundingClientRect();
    const outside = event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom;
    if (outside) closeComposer();
  });
  on(composer, "cancel", (event) => {
    event.preventDefault();
    closeComposer();
  });

  on(document, "keydown", (event) => {
    if (event.key === "Escape") {
      setPublicNav(false);
      setAppNav(false);
    }
    const target = event.target;
    const typing = target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target instanceof HTMLSelectElement || target?.isContentEditable;
    if (event.key === "/" && !typing) {
      const search = document.querySelector('a[href="/app/search"]');
      if (search) {
        event.preventDefault();
        search.click();
      }
    }
  });
})();
