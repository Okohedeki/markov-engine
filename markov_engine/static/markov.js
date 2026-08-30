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
    navToggle.setAttribute("aria-expanded", String(open));
    siteNav.dataset.open = String(open);
  };
  on(navToggle, "click", () => setPublicNav(navToggle.getAttribute("aria-expanded") !== "true"));
  all("[data-site-nav] a").forEach((link) => on(link, "click", () => setPublicNav(false)));

  const appSidebar = document.querySelector("[data-app-sidebar]");
  const appScrim = document.querySelector("[data-app-scrim]");
  const appOpen = document.querySelector("[data-app-nav-open]");
  const appClose = document.querySelector("[data-app-nav-close]");
  const setAppNav = (open) => {
    if (!appSidebar || !appScrim) return;
    appSidebar.dataset.open = String(open);
    appScrim.hidden = !open;
    appOpen?.setAttribute("aria-expanded", String(open));
    if (open) appClose?.focus();
  };
  on(appOpen, "click", () => setAppNav(true));
  on(appClose, "click", () => setAppNav(false));
  on(appScrim, "click", () => setAppNav(false));

  const sourceTabs = all("[data-source-choice]");
  const sourcePlaceholder = document.querySelector("[data-source-placeholder] > span");
  const chooseSource = (tab) => {
    activateTab(sourceTabs, tab);
    if (sourcePlaceholder) sourcePlaceholder.textContent = tab.dataset.placeholder || "Start with a source…";
  };
  sourceTabs.forEach((tab) => on(tab, "click", () => chooseSource(tab)));
  if (sourceTabs.length) bindArrowTabs(sourceTabs, chooseSource);

  all(".mk-capture-types").forEach((group) => {
    const buttons = all("[data-signal-type]", group);
    const form = group.closest("form");
    const input = form?.querySelector("[data-signal-input]");
    buttons.forEach((button) => {
      on(button, "click", () => {
        buttons.forEach((item) => item.setAttribute("aria-pressed", String(item === button)));
        if (input) {
          input.placeholder = button.dataset.placeholder || "Add a source or question…";
          input.focus();
        }
      });
    });
  });

  const routeData = {
    buyers: {
      status: "Supported direction",
      strength: "High information gain",
      title: "Who absorbs gradually weaker Japanese demand?",
      body: "Track the institutions most likely to replace marginal buying, then compare auction demand and sector-level holdings before treating a proposal as a sale.",
      matters: "A slower buyer can change financing conditions before the headline event appears.",
      weakness: "Domestic allocations may change too slowly or be offset by another buyer."
    },
    mandates: {
      status: "Decision-owner route",
      strength: "Focused mechanism",
      title: "Which institution can actually change the flow?",
      body: "Name the mandate owners, implementation dates, and allocation constraints behind the macro claim instead of treating Japan as one investor.",
      matters: "A precise decision owner makes the thesis testable and gives the audience a concrete event to watch.",
      weakness: "A policy statement may never become a material portfolio change."
    },
    hedging: {
      status: "Competing explanation",
      strength: "Medium information gain",
      title: "When does the foreign yield stop being attractive?",
      body: "Compare domestic yields with currency-hedged foreign returns and test whether hedging costs explain the allocation shift better than demographic pressure.",
      matters: "The competing mechanism may predict a different timeline and a different first observable signal.",
      weakness: "Currency costs may be secondary to mandates, regulation, or liquidity needs."
    }
  };
  const routeTabs = all("[data-route-choice]");
  const chooseRoute = (tab) => {
    activateTab(routeTabs, tab);
    const data = routeData[tab.dataset.routeChoice];
    if (!data) return;
    Object.entries(data).forEach(([key, value]) => {
      const target = document.querySelector(`[data-route-${key}]`);
      if (target) target.textContent = value;
    });
  };
  routeTabs.forEach((tab) => on(tab, "click", () => chooseRoute(tab)));
  if (routeTabs.length) bindArrowTabs(routeTabs, chooseRoute);

  const outputData = {
    brief: {
      label: "Decision brief",
      title: "The first Treasury signal may be the buyer who never arrives.",
      copy: "A visible selloff is not required for Japanese allocation changes to matter. Watch marginal demand, institutional mandates, and hedging costs before the dramatic headline.",
      note: "Policy timing is supported. The demand effect remains an interpretation pending aligned flow data."
    },
    research: {
      label: "Research report",
      title: "Three mechanisms could weaken Japanese demand—and they leave different traces.",
      copy: "Separate portfolio mandates, domestic-yield competition, and currency hedging. Compare their decision owners, time horizons, and observable data before choosing one explanation.",
      note: "The mechanisms have credible source support. Their relative size and timing remain unresolved."
    },
    script: {
      label: "Factual script",
      title: "Everyone is watching for a seller. Watch for the missing buyer.",
      copy: "The dramatic version begins with Japan dumping Treasuries. The more useful version begins earlier: domestic returns improve, mandates shift, and marginal demand quietly changes.",
      note: "Ready-to-record language retains the caveat: no completed allocation change has been established."
    }
  };
  const outputTabs = all("[data-output-choice]");
  const chooseOutput = (tab) => {
    activateTab(outputTabs, tab);
    const data = outputData[tab.dataset.outputChoice];
    if (!data) return;
    Object.entries(data).forEach(([key, value]) => {
      const target = document.querySelector(`[data-output-${key}]`);
      if (target) target.textContent = value;
    });
  };
  outputTabs.forEach((tab) => on(tab, "click", () => chooseOutput(tab)));
  if (outputTabs.length) bindArrowTabs(outputTabs, chooseOutput);

  const caseTabs = all("[data-case-view-tab]");
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
        window.scrollTo({ top: 0, behavior: "smooth" });
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
      if (context) context.textContent = `Working from “${button.dataset.topicTitle || "this route"}”.`;
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
