/*
 * The kiosk client: poll the session document and render it.
 *
 * It holds no rule and no copy. Every number, every sentence and every chip comes from the
 * server payload, so the display cannot disagree with the measurement and the tests for both
 * live in Python. This file's only jobs are: request, render, and forward a button press.
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

  var session = null;
  var pollTimer = null;
  var healthTimer = null;
  var busy = false;

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

  function chipFrom(chip) {
    var node = make("span", "chip " + chip.tone);
    node.appendChild(make("i"));
    node.appendChild(document.createTextNode(chip.text));
    return node;
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

  function staffFold(result, colour) {
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
          " s window · " +
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
        drawTrace(spark, colour);
      }
    });
    return details;
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
        var note = make("div", null, "trace unavailable");
        if (canvas.parentNode) {
          canvas.parentNode.appendChild(note);
        }
      });
  }

  function actionRow(kind, result) {
    var row = make("div", "row");
    var button = make("button", "btn");
    button.type = "button";
    if (kind === "start") {
      button.textContent = "Start";
      button.className = "btn";
      button.addEventListener("click", start);
    } else if (kind === "stop") {
      button.textContent = "Stop";
      button.className = "btn ghost";
      button.addEventListener("click", stop);
    } else {
      var irregular = result && result.outcome === "irregular";
      button.textContent = result && result.outcome === "unclear" ? "Try again" : "Done";
      button.className = irregular ? "btn crit" : "btn";
      button.addEventListener("click", done);
    }
    row.appendChild(button);
    return row;
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
    var keyword =
      next.state === "idle"
        ? "Screening station · Bay 1"
        : next.state === "result"
          ? "Result"
          : "Measuring";
    var result = next.result;
    var colour =
      result && result.outcome === "irregular"
        ? token("--crit", "#b3261e")
        : result && result.outcome === "unclear"
          ? token("--warn", "#8f5600")
          : token("--ok", "#0f7b4f");

    clear(panel);
    panel.appendChild(make("div", "state-k", keyword));
    var heading = make("h1");
    if (next.state === "result" && result) {
      heading.className = result.outcome === "regular" ? "ok" : result.outcome === "unclear" ? "warn" : "crit";
    }
    heading.textContent = next.headline;
    panel.appendChild(heading);
    if (next.lede) {
      panel.appendChild(make("p", "lede", next.lede));
    }

    if (next.state === "settle" || next.state === "measuring") {
      var progress = make("div", "prog");
      var bar = make("i");
      bar.style.width = Math.round((next.elapsed_ms / (next.duration_ms || 1)) * 100) + "%";
      progress.appendChild(bar);
      panel.appendChild(progress);
    }

    if (next.chip) {
      panel.appendChild(chipFrom(next.chip));
    }

    if (result) {
      panel.appendChild(metricsFrom(result.metrics));
      panel.appendChild(stepsFrom(next.steps));
      panel.appendChild(staffFold(result, colour));
    } else {
      panel.appendChild(stepsFrom(next.steps));
    }

    if (next.hint) {
      panel.appendChild(make("p", "hint", next.hint));
    }

    if (next.state === "idle") {
      panel.appendChild(actionRow("start"));
    } else if (next.state === "result") {
      panel.appendChild(actionRow("done", result));
    } else {
      panel.appendChild(actionRow("stop"));
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
    fetch(path, { method: "POST", cache: "no-store" })
      .then(function () {
        busy = false;
        refresh();
      })
      .catch(function () {
        busy = false;
        refresh();
      });
  }

  function start() {
    var scenario = new URLSearchParams(window.location.search).get("scenario");
    var path = "/api/v1/session";
    if (scenario) {
      path += "?scenario=" + encodeURIComponent(scenario);
    }
    post(path);
  }

  function stop() {
    post("/api/v1/session/stop");
  }

  function done() {
    post("/api/v1/session/done");
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

  window.Hinigram = { refresh: refresh, render: render, start: start, stop: stop, done: done };
})();
