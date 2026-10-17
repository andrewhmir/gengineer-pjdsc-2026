/*
 * The kiosk client: poll the session document and render it.
 *
 * It holds no rule and no copy. Every number, every sentence and every chip comes from the
 * server payload, so the display cannot disagree with the measurement and the tests for both
 * live in Python. This file's only jobs are: request, render, and forward a button press.
 *
 * The panel is built once per state and updated in place afterwards. Replacing it on every poll
 * destroyed keyboard focus every 250 ms, re-announced the whole panel to a screen reader four
 * times a second, and closed the staff fold within a second of it being opened.
 */
(function () {
  "use strict";

  var POLL_ACTIVE_MS = 250;
  var POLL_IDLE_MS = 1000;
  var POLL_RETRY_MS = 2000;
  var HEALTH_EVERY_MS = 5000;

  var SOURCE_TOKENS = { sim: "SIM", replay: "REPLAY", serial: "LIVE" };

  var panel = document.getElementById("panel");
  var stageTag = document.getElementById("stage-tag");
  var clockEl = document.getElementById("clock");
  var healthWord = document.getElementById("health-word");
  var healthDot = document.getElementById("health-dot");
  var sourceChip = document.getElementById("source-chip");
  var announcer = document.getElementById("announcer");

  var session = null;
  var pollTimer = null;
  var healthTimer = null;
  var busy = false;
  var renderedKey = "";
  var refs = {};

  function make(tag, className, text) {
    var node = document.createElement(tag);
    if (className) {
      node.className = className;
    }
    if (text !== undefined && text !== null) {
      node.textContent = text;
    }
    return node;
  }

  function clear(node) {
    while (node.firstChild) {
      node.removeChild(node.firstChild);
    }
  }

  function token(name, fallback) {
    var value = getComputedStyle(document.documentElement).getPropertyValue(name);
    return value && value.trim() ? value.trim() : fallback;
  }

  function stateKey(next) {
    return (next.state || "") + ":" + (next.id || "");
  }

  function announce(text) {
    if (announcer && text) {
      announcer.textContent = text;
    }
  }

  function stepsFrom(steps) {
    var list = make("ol", "steps");
    (steps || []).forEach(function (step) {
      list.appendChild(make("li", step.status, step.label));
    });
    return list;
  }

  function metricsFrom(metrics) {
    var grid = make("div", "metrics");
    (metrics || []).forEach(function (metric) {
      var card = make("div", "metric");
      card.appendChild(make("div", "k", metric.label));
      var value = make("div", "v", metric.value);
      if (metric.unit) {
        value.appendChild(make("small", null, " " + metric.unit));
      }
      card.appendChild(value);
      grid.appendChild(card);
    });
    return grid;
  }

  function chipInto(slot, chip) {
    clear(slot);
    if (!chip) {
      return;
    }
    var node = make("span", "chip " + chip.tone);
    node.appendChild(make("i"));
    node.appendChild(document.createTextNode(chip.text));
    slot.appendChild(node);
  }

  function drawTrace(canvas, colour) {
    fetch("/api/v1/session/trace", { cache: "no-store" })
      .then(function (response) {
        if (!response.ok) {
          throw new Error("trace unavailable");
        }
        return response.json();
      })
      .then(function (trace) {
        window.Wave.draw(canvas, trace, colour);
      })
      .catch(function () {
        if (canvas.parentNode && !canvas.parentNode.querySelector(".wave-missing")) {
          canvas.parentNode.appendChild(make("div", "wave-missing", "trace unavailable"));
        }
      });
  }

  function staffFold(result) {
    var details = make("details", "staff");
    details.appendChild(make("summary", null, "Details for staff"));
    var body = make("div", "det");
    var detail = result.details;
    body.appendChild(
      document.createTextNode(
        "Phase-locking value " +
          (detail.plv === null ? "—" : detail.plv.toFixed(2)) +
          " against the " +
          detail.plv_threshold.toFixed(2) +
          " threshold · " +
          detail.window_s.toFixed(1) +
          " s of data · " +
          detail.breaths +
          " breaths analysed"
      )
    );
    var spark = make("canvas");
    spark.id = "spark";
    body.appendChild(spark);
    details.appendChild(body);
    details.addEventListener("toggle", function () {
      if (details.open) {
        drawTrace(spark, token("--accent", "#0d6e78"));
      }
    });
    return details;
  }

  function buildPanel(next) {
    clear(panel);
    refs = {};
    var result = next.result;
    var kind =
      next.state === "idle" ? "Screening station" : next.state === "result" ? "Result" : "Measuring";
    panel.appendChild(make("div", "state-k", kind));
    refs.heading = make("h1");
    panel.appendChild(refs.heading);
    refs.lede = make("p", "lede");
    panel.appendChild(refs.lede);
    if (next.state === "settle" || next.state === "measuring") {
      refs.progress = make("div", "prog");
      refs.bar = make("i");
      refs.progress.appendChild(refs.bar);
      panel.appendChild(refs.progress);
    }
    refs.chipSlot = make("div", "chip-slot");
    panel.appendChild(refs.chipSlot);
    if (result) {
      panel.appendChild(metricsFrom(result.metrics));
    }
    panel.appendChild(stepsFrom(next.steps));
    if (result) {
      panel.appendChild(staffFold(result));
    }
    refs.hint = make("p", "hint");
    panel.appendChild(refs.hint);
    refs.row = make("div", "row");
    refs.button = make("button", "btn");
    refs.button.type = "button";
    refs.button.addEventListener("click", onAction);
    refs.row.appendChild(refs.button);
    panel.appendChild(refs.row);
  }

  function updatePanel(next) {
    var result = next.result;
    refs.heading.textContent = next.headline;
    refs.heading.className =
      next.state === "result" && result
        ? result.outcome === "regular"
          ? "ok"
          : result.outcome === "unclear"
            ? "warn"
            : "crit"
        : "";
    refs.lede.textContent = next.lede || "";
    if (refs.bar) {
      refs.bar.style.width =
        Math.round((next.elapsed_ms / (next.duration_ms || 1)) * 100) + "%";
    }
    chipInto(refs.chipSlot, next.chip);
    refs.hint.textContent = next.hint || "";
    refs.hint.className = next.hint ? "hint" : "hidden";
    if (next.state === "idle") {
      refs.action = "start";
      refs.button.textContent = "Start";
      refs.button.className = "btn";
    } else if (next.state === "result") {
      refs.action = "done";
      refs.button.textContent = "Done";
      refs.button.className = result && result.outcome === "irregular" ? "btn crit" : "btn";
    } else {
      refs.action = "stop";
      refs.button.textContent = "Stop";
      refs.button.className = "btn ghost";
    }
  }

  function render(next) {
    session = next;
    if (sourceChip && SOURCE_TOKENS[next.source]) {
      sourceChip.textContent = SOURCE_TOKENS[next.source];
    }
    if (window.StationScene) {
      window.StationScene.setState(next);
    }
    if (!panel) {
      return;
    }
    var key = stateKey(next);
    if (key !== renderedKey) {
      var focused = document.activeElement && document.activeElement.dataset
        ? document.activeElement.dataset.action
        : null;
      buildPanel(next);
      renderedKey = key;
      announce(
        next.state === "result"
          ? next.headline
          : next.state === "measuring"
            ? "Measuring. Stand still."
            : next.state === "idle"
              ? "Ready. Step onto the mark and press Start."
              : "Checking that you are standing still."
      );
      if (focused) {
        var target = panel.querySelector('[data-action="' + focused + '"]');
        if (target) {
          target.focus();
        }
      }
    }
    updatePanel(next);
    if (refs.button) {
      refs.button.dataset.action = refs.action || "";
    }
  }

  function onAction() {
    if (refs.action === "start") {
      start();
    } else if (refs.action === "stop") {
      post("/api/v1/session/stop");
    } else {
      post("/api/v1/session/done");
    }
  }

  function nextDelay() {
    var state = session && session.state;
    return state === "settle" || state === "measuring" ? POLL_ACTIVE_MS : POLL_IDLE_MS;
  }

  function schedule(delay) {
    if (pollTimer) {
      clearTimeout(pollTimer);
    }
    pollTimer = setTimeout(poll, delay);
  }

  function poll() {
    fetch("/api/v1/session", { cache: "no-store" })
      .then(function (response) {
        if (!response.ok) {
          throw new Error("session unavailable");
        }
        return response.json();
      })
      .then(function (payload) {
        render(payload);
        schedule(nextDelay());
      })
      .catch(function () {
        if (healthWord) {
          healthWord.textContent = "Reconnecting…";
        }
        if (healthDot) {
          healthDot.className = "dot warn";
        }
        schedule(POLL_RETRY_MS);
      });
  }

  function refresh() {
    if (pollTimer) {
      clearTimeout(pollTimer);
    }
    poll();
  }

  function post(path) {
    if (busy) {
      return;
    }
    busy = true;
    if (refs.button) {
      refs.button.disabled = true;
    }
    fetch(path, { method: "POST", cache: "no-store" })
      .then(function (response) {
        if (!response.ok) {
          throw new Error("the station refused that request");
        }
        busy = false;
        refresh();
      })
      .catch(function () {
        busy = false;
        if (refs.button) {
          refs.button.disabled = false;
        }
        announce("The station could not do that. Try again.");
        refresh();
      });
  }

  function start() {
    var scenario = new URLSearchParams(window.location.search).get("scenario");
    var path = "/api/v1/session";
    // The demo control exists only on the simulator; sending it to a recording or a live
    // receiver would be refused and the Start button would appear dead.
    if (scenario && session && session.source === "sim") {
      path += "?scenario=" + encodeURIComponent(scenario);
    }
    post(path);
  }

  function health() {
    fetch("/healthz/station", { cache: "no-store" })
      .then(function (response) {
        return response.json();
      })
      .then(function (payload) {
        if (healthWord) {
          healthWord.textContent = payload.ok ? "Station ready" : payload.detail;
        }
        if (healthDot) {
          healthDot.className = payload.ok ? "dot" : "dot warn";
        }
      })
      .catch(function () {
        if (healthWord) {
          healthWord.textContent = "Source offline";
        }
        if (healthDot) {
          healthDot.className = "dot warn";
        }
      });
  }

  function tickClock() {
    if (clockEl) {
      clockEl.textContent = new Date().toLocaleTimeString("en-GB", { hour12: false });
    }
  }

  function boot() {
    var canvas = document.getElementById("stage");
    if (canvas && window.StationScene) {
      window.StationScene.init(canvas);
    }
    tickClock();
    setInterval(tickClock, 1000);
    health();
    healthTimer = setInterval(health, HEALTH_EVERY_MS);
    poll();
    window.addEventListener("pagehide", function () {
      if (pollTimer) {
        clearTimeout(pollTimer);
      }
      if (healthTimer) {
        clearInterval(healthTimer);
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }

  window.Hinigram = { refresh: refresh, render: render, start: start };
})();
