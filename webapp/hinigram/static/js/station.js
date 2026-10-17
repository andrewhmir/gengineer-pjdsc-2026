/*
 * The station scene: the floor, the four radio masts, the mark, and an abstract figure.
 *
 * This is a diagram, not a camera. Nothing here is a photograph or a reconstruction of a person:
 * the figure is drawn from the rate the station measured, and the caption above it says so, which
 * is a requirement rather than a courtesy (REQ-119).
 *
 * Geometry: a perspective projection with painter's ordering — no WebGL, no library, no build
 * step. The rig constants are the three transmitters and the receiver, in metres, from the
 * design record; moving the hardware means editing them here.
 */
(function () {
  "use strict";

  var TWOPI = Math.PI * 2;

  var RIG = [
    { id: "TX-1", x: -1.55, z: -1.1 },
    { id: "TX-2", x: 1.55, z: -1.1 },
    { id: "TX-3", x: 0.1, z: -1.95 },
    { id: "RX", x: 1.6, z: 1.25 }
  ];

  var CAM = { yaw: -0.34, pitch: 0.54, dist: 7.4, f: 800, tx: 0, ty: 0.82, tz: 0.15 };
  var FLOOR = { x0: -2.2, x1: 2.2, z0: -2.2, z1: 2.2 };
  var MARK_R = 0.62;

  var canvas = null;
  var ctx = null;
  var W = 0;
  var H = 0;
  var DPR = 1;
  var state = { state: "idle", elapsed_ms: 0, duration_ms: 33000, live: null, result: null };
  var palette = {};
  var reducedMotion = false;
  var frameHandle = null;
  var dragging = false;
  var lastPointer = null;
  var origin = { yaw: CAM.yaw, pitch: CAM.pitch };

  function readPalette() {
    var style = getComputedStyle(document.documentElement);
    function token(name, fallback) {
      var value = style.getPropertyValue(name);
      return value && value.trim() ? value.trim() : fallback;
    }
    palette = {
      ink: token("--ink", "#0e1a28"),
      muted: token("--muted", "#5b6b7d"),
      faint: token("--faint", "#8697a9"),
      line: token("--line", "#dfe6ee"),
      accent: token("--accent", "#0d6e78"),
      ok: token("--ok", "#0f7b4f"),
      warn: token("--warn", "#8f5600"),
      crit: token("--crit", "#b3261e")
    };
  }

  function rgba(hex, alpha) {
    var value = hex.replace("#", "");
    if (value.length === 3) {
      value = value[0] + value[0] + value[1] + value[1] + value[2] + value[2];
    }
    var number = parseInt(value, 16);
    return (
      "rgba(" + ((number >> 16) & 255) + "," + ((number >> 8) & 255) + "," + (number & 255) +
      "," + alpha + ")"
    );
  }

  function project(p) {
    var x = p[0] - CAM.tx;
    var y = p[1] - CAM.ty;
    var z = p[2] - CAM.tz;
    var cy = Math.cos(CAM.yaw);
    var sy = Math.sin(CAM.yaw);
    var x1 = x * cy - z * sy;
    var z1 = x * sy + z * cy;
    var cp = Math.cos(CAM.pitch);
    var sp = Math.sin(CAM.pitch);
    var y2 = y * cp - z1 * sp;
    var z2 = y * sp + z1 * cp;
    var z3 = z2 + CAM.dist;
    var scale = CAM.f / Math.max(0.2, z3);
    return { x: W / 2 + x1 * scale, y: H * 0.6 - y2 * scale, z: z3, s: scale };
  }

  function poly(points, fill, stroke, width) {
    ctx.beginPath();
    for (var i = 0; i < points.length; i += 1) {
      var q = project(points[i]);
      if (i) {
        ctx.lineTo(q.x, q.y);
      } else {
        ctx.moveTo(q.x, q.y);
      }
    }
    ctx.closePath();
    if (fill) {
      ctx.fillStyle = fill;
      ctx.fill();
    }
    if (stroke) {
      ctx.strokeStyle = stroke;
      ctx.lineWidth = width || 1;
      ctx.stroke();
    }
  }

  function floorArc(cx, cz, radius, from, to, stroke, width, dash) {
    var count = Math.max(8, Math.round((to - from) / 0.12));
    var points = [];
    for (var i = 0; i <= count; i += 1) {
      var angle = from + ((to - from) * i) / count;
      points.push([cx + Math.cos(angle) * radius, 0.015, cz + Math.sin(angle) * radius]);
    }
    if (dash) {
      ctx.setLineDash(dash);
    } else {
      ctx.setLineDash([]);
    }
    ctx.beginPath();
    for (var j = 0; j < points.length; j += 1) {
      var q = project(points[j]);
      if (j) {
        ctx.lineTo(q.x, q.y);
      } else {
        ctx.moveTo(q.x, q.y);
      }
    }
    ctx.strokeStyle = stroke;
    ctx.lineWidth = width;
    ctx.stroke();
    ctx.setLineDash([]);
  }

  function floorDisc(cx, cz, radius, fill) {
    var centre = project([cx, 0.012, cz]);
    var edgeX = project([cx + radius, 0.012, cz]);
    var edgeZ = project([cx, 0.012, cz + radius]);
    ctx.save();
    ctx.transform(
      edgeX.x - centre.x,
      edgeX.y - centre.y,
      edgeZ.x - centre.x,
      edgeZ.y - centre.y,
      centre.x,
      centre.y
    );
    ctx.beginPath();
    ctx.arc(0, 0, 1, 0, TWOPI);
    ctx.restore();
    ctx.fillStyle = fill;
    ctx.fill();
  }

  function drawFloor() {
    poly(
      [
        [FLOOR.x0, 0, FLOOR.z0],
        [FLOOR.x1, 0, FLOOR.z0],
        [FLOOR.x1, 0, FLOOR.z1],
        [FLOOR.x0, 0, FLOOR.z1]
      ],
      rgba(palette.accent, 0.01),
      palette.line,
      1
    );
    ctx.strokeStyle = rgba(palette.line, 0.55);
    ctx.lineWidth = 1;
    for (var grid = FLOOR.x0; grid <= FLOOR.x1 + 1e-6; grid += 0.5) {
      var a = project([grid, 0, FLOOR.z0]);
      var b = project([grid, 0, FLOOR.z1]);
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
      ctx.stroke();
      var c = project([FLOOR.x0, 0, grid]);
      var d = project([FLOOR.x1, 0, grid]);
      ctx.beginPath();
      ctx.moveTo(c.x, c.y);
      ctx.lineTo(d.x, d.y);
      ctx.stroke();
    }
  }

  function progress() {
    var duration = state.duration_ms || 1;
    return Math.min(1, Math.max(0, (state.elapsed_ms || 0) / duration));
  }

  function outcomeColour() {
    var result = state.result;
    if (!result) {
      return palette.accent;
    }
    if (result.outcome === "regular") {
      return palette.ok;
    }
    if (result.outcome === "irregular") {
      return palette.crit;
    }
    return palette.warn;
  }

  function drawMark(now) {
    var measuring = state.state === "measuring";
    var finished = state.state === "result";
    if (state.state === "idle") {
      floorArc(0, 0, MARK_R, 0, TWOPI, rgba(palette.accent, 0.55), 2, [6, 6]);
      floorDisc(0, 0, 0.16, rgba(palette.accent, 0.1));
      return;
    }
    floorArc(0, 0, MARK_R, 0, TWOPI, rgba(palette.accent, 0.18), 2, null);
    floorDisc(0, 0, 0.3, rgba(palette.accent, 0.05));
    if (measuring && progress() > 0.01) {
      floorArc(0, 0, 0.78, Math.PI / 2, Math.PI / 2 + TWOPI * progress(), palette.accent, 4, null);
    }
    if (finished) {
      var colour = outcomeColour();
      var pulse = reducedMotion ? 1 : 0.55 + 0.45 * Math.abs(Math.sin(now / 700));
      floorDisc(0, 0, 1.05, rgba(colour, 0.05 + 0.04 * pulse));
      floorArc(0, 0, 0.86, 0, TWOPI, rgba(colour, 0.55 + 0.35 * pulse), 2.5, null);
    }
  }

  function drawNode(node) {
    var base = project([node.x, 0, node.z]);
    var top = project([node.x, 1.05, node.z]);
    ctx.strokeStyle = rgba(palette.faint, 0.75);
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(base.x, base.y);
    ctx.lineTo(top.x, top.y);
    ctx.stroke();
    var width = Math.max(9, 0.1 * top.s);
    var height = width * 0.8;
    ctx.beginPath();
    ctx.roundRect(top.x - width / 2, top.y - height, width, height, 2);
    ctx.fillStyle = palette.ink;
    ctx.fill();
    ctx.fillStyle = palette.faint;
    ctx.font = '600 16px "Inter", "Segoe UI", system-ui, sans-serif';
    ctx.textAlign = "center";
    ctx.fillText(node.id, top.x, top.y - height - 8);
  }

  function drawPerson(breath, outcome) {
    var feet = project([0, 0, 0.05]);
    var s = feet.s;
    var hipY = feet.y - 0.86 * s;
    var shoulderY = feet.y - 1.44 * s;
    var headY = feet.y - 1.6 * s;
    var chest = 1 + 0.028 * breath;
    var shadow = project([0, 0.01, 0.05]);
    ctx.save();
    ctx.beginPath();
    ctx.ellipse(shadow.x, shadow.y, 0.3 * s, 0.1 * s, 0, 0, TWOPI);
    ctx.fillStyle = rgba(palette.ink, 0.07);
    ctx.fill();
    ctx.restore();
    ctx.fillStyle = rgba(palette.faint, 0.55);
    ctx.beginPath();
    ctx.roundRect(feet.x - 0.085 * s, hipY, 0.075 * s, feet.y - hipY - 2, 3);
    ctx.fill();
    ctx.beginPath();
    ctx.roundRect(feet.x + 0.01 * s, hipY, 0.075 * s, feet.y - hipY - 2, 3);
    ctx.fill();
    ctx.beginPath();
    ctx.roundRect(feet.x - 0.245 * s, shoulderY + 0.02 * s, 0.07 * s, 0.52 * s, 4);
    ctx.fill();
    ctx.beginPath();
    ctx.roundRect(feet.x + 0.175 * s, shoulderY + 0.02 * s, 0.07 * s, 0.52 * s, 4);
    ctx.fill();
    var torsoWidth = 0.34 * s * chest;
    ctx.beginPath();
    ctx.roundRect(feet.x - torsoWidth / 2, shoulderY, torsoWidth, hipY - shoulderY + 0.06 * s, 8);
    ctx.fillStyle = rgba(palette.faint, 0.32);
    ctx.fill();
    ctx.strokeStyle = outcome ? rgba(outcome, 0.85) : rgba(palette.faint, 0.55);
    ctx.lineWidth = outcome ? 2 : 1;
    ctx.stroke();
    ctx.beginPath();
    ctx.roundRect(feet.x - 0.035 * s, headY + 0.1 * s, 0.07 * s, 0.09 * s, 2);
    ctx.fillStyle = rgba(palette.faint, 0.55);
    ctx.fill();
    ctx.beginPath();
    ctx.arc(feet.x, headY, 0.115 * s, 0, TWOPI);
    ctx.fillStyle = rgba(palette.faint, 0.45);
    ctx.fill();
    ctx.strokeStyle = rgba(palette.faint, 0.6);
    ctx.lineWidth = 1;
    ctx.stroke();
  }

  function drawTag() {
    var result = state.result;
    if (!result || state.state !== "result") {
      return;
    }
    var word =
      result.outcome === "regular"
        ? "REGULAR"
        : result.outcome === "irregular"
          ? "IRREGULAR"
          : "NOT CLEAR";
    var label = word;
    if (result.rr_bpm !== null && result.rr_bpm !== undefined) {
      label += " · " + result.rr_bpm.toFixed(1) + " /min";
    }
    ctx.font = '700 16px "Inter", "Segoe UI", system-ui, sans-serif';
    var width = ctx.measureText(label).width + 24;
    var height = 30;
    var head = project([0, 1.76, 0.05]);
    var x = Math.max(8, Math.min(W - width - 8, head.x - width / 2));
    var y = Math.max(8, head.y - height - 18);
    ctx.beginPath();
    ctx.moveTo(x + 6, y);
    ctx.lineTo(x + width - 6, y);
    ctx.quadraticCurveTo(x + width, y, x + width, y + 6);
    ctx.lineTo(x + width, y + height - 6);
    ctx.quadraticCurveTo(x + width, y + height, x + width - 6, y + height);
    ctx.lineTo(x + 6, y + height);
    ctx.quadraticCurveTo(x, y + height, x, y + height - 6);
    ctx.lineTo(x, y + 6);
    ctx.quadraticCurveTo(x, y, x + 6, y);
    ctx.closePath();
    ctx.fillStyle = outcomeColour();
    ctx.fill();
    ctx.beginPath();
    ctx.moveTo(head.x, y + height);
    ctx.lineTo(head.x, head.y - 8);
    ctx.strokeStyle = rgba(outcomeColour(), 0.5);
    ctx.lineWidth = 1;
    ctx.stroke();
    ctx.fillStyle = "#ffffff";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(label, x + width / 2, y + height / 2 + 1);
    ctx.textBaseline = "alphabetic";
  }

  function breathingPhase(now) {
    var rr = (state.live && state.live.rr_bpm) || 15;
    return Math.sin(TWOPI * (rr / 60) * (now / 1000));
  }

  function draw(now) {
    if (!ctx || !W || !H) {
      frameHandle = requestAnimationFrame(draw);
      return;
    }
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    ctx.clearRect(0, 0, W, H);
    drawFloor();
    drawMark(now);
    for (var i = 0; i < RIG.length; i += 1) {
      drawNode(RIG[i]);
    }
    if (state.state === "measuring" || state.state === "result" || state.state === "settle") {
      var outcome = state.state === "result" ? outcomeColour() : null;
      var breath = reducedMotion ? 0 : breathingPhase(now);
      drawPerson(breath, outcome);
      drawTag();
    }
    frameHandle = requestAnimationFrame(draw);
  }

  function resize() {
    if (!canvas) {
      return;
    }
    DPR = window.devicePixelRatio || 1;
    W = canvas.clientWidth || 600;
    H = canvas.clientHeight || 430;
    canvas.width = Math.round(W * DPR);
    canvas.height = Math.round(H * DPR);
    readPalette();
  }

  function onPointerDown(event) {
    dragging = true;
    lastPointer = { x: event.clientX, y: event.clientY, yaw: CAM.yaw, pitch: CAM.pitch };
  }

  function onPointerMove(event) {
    if (!dragging || !lastPointer) {
      return;
    }
    var dx = (event.clientX - lastPointer.x) / 260;
    var dy = (event.clientY - lastPointer.y) / 620;
    CAM.yaw = Math.max(origin.yaw - 0.5, Math.min(origin.yaw + 0.5, lastPointer.yaw + dx));
    CAM.pitch = Math.max(origin.pitch - 0.15, Math.min(origin.pitch + 0.15, lastPointer.pitch + dy));
  }

  function onPointerUp() {
    dragging = false;
    lastPointer = null;
  }

  function onDoubleClick() {
    CAM.yaw = origin.yaw;
    CAM.pitch = origin.pitch;
  }

  function init(element) {
    canvas = element;
    ctx = canvas.getContext("2d");
    reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    readPalette();
    resize();
    if (window.ResizeObserver) {
      new ResizeObserver(resize).observe(canvas);
    } else {
      window.addEventListener("resize", resize);
    }
    canvas.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
    canvas.addEventListener("dblclick", onDoubleClick);
    window.addEventListener("pagehide", function () {
      if (frameHandle) {
        cancelAnimationFrame(frameHandle);
        frameHandle = null;
      }
    });
    if (frameHandle === null) {
      frameHandle = requestAnimationFrame(draw);
    }
  }

  function setState(next) {
    state = next;
    var tag = document.getElementById("stage-tag");
    if (tag && next && next.stage_label) {
      tag.textContent = next.stage_label;
    }
  }

  window.StationScene = { init: init, setState: setState };
})();
