/*
 * The rhythm strip in the staff fold: the measured respiratory signal, not a decoration.
 *
 * It draws the trace the server measured — the bandpassed phase modulation — so a member of
 * staff looking at a flagged result sees the waveform that produced it. If there is no trace,
 * the canvas stays empty and the caller says so; nothing here invents a curve.
 */
(function () {
  "use strict";

  function fit(canvas) {
    var ratio = window.devicePixelRatio || 1;
    var width = canvas.clientWidth || 320;
    var height = canvas.clientHeight || 56;
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
    var ctx = canvas.getContext("2d");
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    return { ctx: ctx, width: width, height: height };
  }

  function draw(canvas, trace, colour) {
    if (!canvas || !trace || !trace.amp || !trace.amp.length) {
      return;
    }
    var surface = fit(canvas);
    var ctx = surface.ctx;
    var width = surface.width;
    var height = surface.height;
    var values = trace.amp;
    var peak = 0;
    for (var i = 0; i < values.length; i += 1) {
      peak = Math.max(peak, Math.abs(values[i]));
    }
    var scale = peak > 0 ? (height * 0.38) / peak : 0;
    ctx.clearRect(0, 0, width, height);
    ctx.strokeStyle = "rgba(134, 151, 169, 0.45)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, height / 2);
    ctx.lineTo(width, height / 2);
    ctx.stroke();
    ctx.beginPath();
    for (var index = 0; index < values.length; index += 1) {
      var x = (index / (values.length - 1 || 1)) * width;
      var y = height / 2 - values[index] * scale;
      if (index) {
        ctx.lineTo(x, y);
      } else {
        ctx.moveTo(x, y);
      }
    }
    ctx.strokeStyle = colour || "rgba(13, 110, 120, 0.9)";
    ctx.lineWidth = 1.6;
    ctx.stroke();
  }

  window.Wave = { draw: draw };
})();
