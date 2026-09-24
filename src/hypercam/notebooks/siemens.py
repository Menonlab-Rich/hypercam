# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "anywidget>=0.9.18",
#     "marimo>=0.24.2",
#     "matplotlib>=3.9.0",
#     "numpy>=2.0.0",
#     "opencv-python-headless>=4.10.0",
#     "pint>=0.26.1",
#     "traitlets>=5.14.0",
# ]
# ///

import marimo

__generated_with = "0.24.2"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _():
    import base64
    import csv
    import io
    import math
    import os
    import tempfile

    import anywidget
    import cv2
    import marimo as mo
    import matplotlib.pyplot as plt
    import numpy as np
    import pint
    import traitlets

    ureg = pint.UnitRegistry()
    return (
        anywidget,
        base64,
        csv,
        cv2,
        io,
        math,
        mo,
        np,
        os,
        plt,
        tempfile,
        traitlets,
        ureg,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Siemens-star resolution from color event video

    Upload a rendered event-camera video (green positive events and orange
    negative events) and the chart image that was uniformly fit to the
    monitor. Annotate the same visible radial boundaries in both views.

    The method assumes a near fronto-parallel view (translation, rotation,
    and uniform scale). A strongly oblique view needs projective calibration.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    monitor_diagonal_in = mo.ui.number(start=1, stop=100, step=0.1, value=25.1, label="Monitor diagonal (in)")
    monitor_width_px = mo.ui.number(start=1, step=1, value=1920, label="Monitor width (px)")
    monitor_height_px = mo.ui.number(start=1, step=1, value=1080, label="Monitor height (px)")
    camera_pitch_um = mo.ui.number(start=0.1, stop=100, step=0.01, value=4.86, label="Camera pitch (µm)")
    mo.vstack([
        mo.md("## 1. Calibration and files"),
        mo.hstack([monitor_diagonal_in, monitor_width_px, monitor_height_px, camera_pitch_um], widths="equal"),
    ])
    return (
        camera_pitch_um,
        monitor_diagonal_in,
        monitor_height_px,
        monitor_width_px,
    )


@app.cell(hide_code=True)
def _(
    camera_pitch_um,
    math,
    monitor_diagonal_in,
    monitor_height_px,
    monitor_width_px,
    ureg,
):
    _diagonal = math.hypot(monitor_width_px.value, monitor_height_px.value)
    monitor_pitch = (monitor_diagonal_in.value * ureg.inch / _diagonal).to("micrometer")
    camera_pitch = camera_pitch_um.value * ureg.micrometer
    return camera_pitch, monitor_pitch


@app.cell(hide_code=True)
def _(mo, monitor_pitch):
    video_file = mo.ui.file(filetypes=["video/*", ".avi", ".mkv", ".mov", ".mp4"], kind="area", max_size=1_500_000_000, label="Event-camera video")
    reference_file = mo.ui.file(filetypes=["image/*", ".bmp", ".jpeg", ".jpg", ".png", ".tif", ".tiff"], kind="area", max_size=100_000_000, label="Reference Siemens chart")
    frame_window = mo.ui.range_slider(start=0, stop=100, step=1, value=[0, 100], show_value=True, label="Video interval (%)")
    sample_count = mo.ui.slider(start=20, stop=400, step=10, value=120, show_value=True, label="Maximum sampled frames")
    mo.vstack([
        mo.hstack([video_file, reference_file], widths="equal"),
        mo.hstack([frame_window, sample_count], widths="equal"),
        mo.md(f"Monitor pixel pitch: **{monitor_pitch.magnitude:.3f} µm/px**"),
    ])
    return frame_window, reference_file, sample_count, video_file


@app.cell
def _(
    cv2,
    frame_window,
    np,
    os,
    reference_file,
    sample_count,
    tempfile,
    video_file,
):
    def decode_image(upload):
        if not upload.value:
            return None
        return cv2.imdecode(np.frombuffer(upload.contents(), dtype=np.uint8), cv2.IMREAD_COLOR)

    def sample_video(upload, percent_window, maximum_frames):
        if not upload.value:
            return [], {}
        _suffix = os.path.splitext(upload.name() or "video.mp4")[1] or ".mp4"
        _path = None
        _frames = []
        try:
            with tempfile.NamedTemporaryFile(suffix=_suffix, delete=False) as _tmp:
                _tmp.write(upload.contents())
                _path = _tmp.name
            _cap = cv2.VideoCapture(_path)
            if not _cap.isOpened():
                raise ValueError("OpenCV could not open the uploaded video")
            _total = max(0, int(_cap.get(cv2.CAP_PROP_FRAME_COUNT)))
            _fps = float(_cap.get(cv2.CAP_PROP_FPS))
            _width = int(_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            _height = int(_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            if _total <= 0:
                raise ValueError("The video does not report a usable frame count")
            _lo = int((_total - 1) * percent_window[0] / 100)
            _hi = int((_total - 1) * percent_window[1] / 100)
            _indices = np.unique(np.linspace(_lo, max(_lo, _hi), min(maximum_frames, _hi - _lo + 1)).astype(int))
            for _index in _indices:
                _cap.set(cv2.CAP_PROP_POS_FRAMES, int(_index))
                _ok, _frame = _cap.read()
                if _ok and _frame is not None:
                    _frames.append(_frame)
            _cap.release()
            return _frames, {
                "total_frames": _total,
                "sampled_frames": len(_frames),
                "fps": _fps,
                "width": _width,
                "height": _height,
                "duration_s": _total / _fps if _fps > 0 else float("nan"),
                "first_index": int(_indices[0]) if len(_indices) else None,
                "last_index": int(_indices[-1]) if len(_indices) else None,
            }
        finally:
            if _path is not None and os.path.exists(_path):
                os.unlink(_path)

    reference_bgr = decode_image(reference_file)
    try:
        video_frames, video_metadata = sample_video(video_file, frame_window.value, sample_count.value)
        video_error = None
    except Exception as _exc:
        video_frames, video_metadata, video_error = [], {}, str(_exc)
    return reference_bgr, video_error, video_frames, video_metadata


@app.cell
def _(cv2, np, video_frames):
    def circular_hue_mode(hues, lo, hi, fallback):
        _selected = hues[(hues >= lo) & (hues <= hi)]
        if _selected.size < 20:
            return fallback
        _hist = np.bincount(_selected.astype(np.int32), minlength=180)
        return int(np.argmax(np.convolve(_hist, np.ones(5), mode="same")))

    if video_frames:
        _pixels = []
        for _frame in video_frames[::max(1, len(video_frames) // 12)]:
            _small = cv2.resize(_frame, None, fx=0.25, fy=0.25, interpolation=cv2.INTER_AREA)
            _hsv = cv2.cvtColor(_small, cv2.COLOR_BGR2HSV)
            _pixels.append(_hsv[(_hsv[..., 1] > 70) & (_hsv[..., 2] > 40), 0])
        _hues = np.concatenate(_pixels) if any(_p.size for _p in _pixels) else np.array([])
        auto_green_hue = circular_hue_mode(_hues, 35, 95, 60)
        auto_orange_hue = circular_hue_mode(_hues, 0, 30, 15)
    else:
        auto_green_hue, auto_orange_hue = 60, 15
    return auto_green_hue, auto_orange_hue


@app.cell(hide_code=True)
def _(auto_green_hue, auto_orange_hue, mo):
    green_hue = mo.ui.slider(0, 179, value=auto_green_hue, show_value=True, label="Green hue center")
    orange_hue = mo.ui.slider(0, 179, value=auto_orange_hue, show_value=True, label="Orange hue center")
    hue_tolerance = mo.ui.slider(1, 40, value=14, show_value=True, label="Hue tolerance")
    minimum_saturation = mo.ui.slider(0, 255, value=70, show_value=True, label="Minimum saturation")
    minimum_value = mo.ui.slider(0, 255, value=35, show_value=True, label="Minimum value")
    activity_floor = mo.ui.slider(0, 80, value=10, show_value=True, label="Reject lowest activity (%)")
    mo.vstack([
        mo.md("## 2. Polarity segmentation"),
        mo.md("Hue centers are initialized from saturated pixels. Adjust the controls until the previews isolate green and orange events."),
        mo.hstack([green_hue, orange_hue, hue_tolerance], widths="equal"),
        mo.hstack([minimum_saturation, minimum_value, activity_floor], widths="equal"),
    ])
    return (
        activity_floor,
        green_hue,
        hue_tolerance,
        minimum_saturation,
        minimum_value,
        orange_hue,
    )


@app.cell
def _(
    activity_floor,
    cv2,
    green_hue,
    hue_tolerance,
    minimum_saturation,
    minimum_value,
    np,
    orange_hue,
    video_frames,
):
    def hue_distance(channel, center):
        _delta = np.abs(channel.astype(np.int16) - int(center))
        return np.minimum(_delta, 180 - _delta)

    _green_list, _orange_list = [], []
    for _frame in video_frames:
        _hsv = cv2.cvtColor(_frame, cv2.COLOR_BGR2HSV)
        _chroma = (_hsv[..., 1] >= minimum_saturation.value) & (_hsv[..., 2] >= minimum_value.value)
        _green_list.append(_chroma & (hue_distance(_hsv[..., 0], green_hue.value) <= hue_tolerance.value))
        _orange_list.append(_chroma & (hue_distance(_hsv[..., 0], orange_hue.value) <= hue_tolerance.value))

    if _green_list:
        _activity = np.array([int(_g.sum() + _o.sum()) for _g, _o in zip(_green_list, _orange_list)])
        _cut = np.percentile(_activity, activity_floor.value)
        valid_frame_mask = _activity > max(0, _cut)
        if not np.any(valid_frame_mask):
            valid_frame_mask = _activity > 0
        green_masks = np.stack(_green_list)[valid_frame_mask]
        orange_masks = np.stack(_orange_list)[valid_frame_mask]
        green_count = green_masks.sum(axis=0).astype(np.float32)
        orange_count = orange_masks.sum(axis=0).astype(np.float32)
        _scale = max(float(np.percentile(green_count + orange_count, 99.5)), 1.0)
        event_composite_rgb = np.zeros((*green_count.shape, 3), dtype=np.uint8)
        event_composite_rgb[..., 1] = np.clip(255 * green_count / _scale, 0, 255).astype(np.uint8)
        event_composite_rgb[..., 0] = np.clip(255 * orange_count / _scale, 0, 255).astype(np.uint8)
        event_composite_rgb[..., 1] = np.maximum(event_composite_rgb[..., 1], np.clip(130 * orange_count / _scale, 0, 130).astype(np.uint8))
    else:
        valid_frame_mask = np.array([], dtype=bool)
        green_masks = np.empty((0, 0, 0), dtype=bool)
        orange_masks = np.empty((0, 0, 0), dtype=bool)
        green_count = orange_count = event_composite_rgb = None
    return (
        event_composite_rgb,
        green_count,
        green_masks,
        orange_count,
        orange_masks,
    )


@app.cell(hide_code=True)
def _(
    event_composite_rgb,
    green_count,
    mo,
    orange_count,
    reference_bgr,
    video_error,
    video_metadata,
):
    _items = []
    if video_error:
        _items.append(mo.callout(video_error, kind="danger", title="Video error"))
    elif event_composite_rgb is None:
        _items.append(mo.callout("Upload a video to begin.", kind="info"))
    else:
        _meta = video_metadata
        _items.extend([
            mo.md(f"Decoded **{_meta['sampled_frames']}** sampled frames from {_meta['total_frames']} total at {_meta['fps']:.3g} fps; size {_meta['width']}×{_meta['height']}."),
            mo.hstack([
                mo.image(event_composite_rgb, caption="Accumulated polarity composite"),
                mo.image(green_count, caption="Green positive-event count"),
                mo.image(orange_count, caption="Orange negative-event count"),
            ], widths="equal"),
        ])
    if reference_bgr is None:
        _items.append(mo.callout("Upload the reference chart image.", kind="info"))
    mo.vstack(_items)
    return


@app.cell
def _(anywidget, base64, cv2, np, traitlets):
    def image_to_data_url(image_rgb):
        _ok, _png = cv2.imencode(".png", cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR))
        if not _ok:
            raise ValueError("Could not encode annotation image")
        return "data:image/png;base64," + base64.b64encode(_png.tobytes()).decode("ascii")

    class PointPicker(anywidget.AnyWidget):
        _esm = r"""
        function render({ model, el }) {
          el.classList.add("siemens-picker");
          const toolbar = document.createElement("div"); toolbar.className = "toolbar";
          const mode = document.createElement("select");
          mode.innerHTML = '<option value="boundary">Boundary points</option><option value="alignment">Alignment landmarks</option>';
          mode.value = model.get("mode");
          const group = document.createElement("input"); group.type = "number"; group.min = "0"; group.step = "1"; group.value = model.get("group"); group.title = "Boundary ID";
          const next = document.createElement("button"); next.textContent = "Next boundary";
          const undo = document.createElement("button"); undo.textContent = "Undo";
          const reset = document.createElement("button"); reset.textContent = "Reset mode";
          const status = document.createElement("span"); status.className = "status";
          toolbar.append("Mode: ", mode, " Boundary ID: ", group, next, undo, reset, status);
          const canvas = document.createElement("canvas"); const ctx = canvas.getContext("2d"); const img = new Image();
          el.replaceChildren(toolbar, canvas);
          function redraw() {
            if (!img.complete || !img.naturalWidth) return;
            canvas.width = img.naturalWidth; canvas.height = img.naturalHeight; ctx.drawImage(img, 0, 0);
            const pts = model.get("points") || []; const palette = ["#00e5ff", "#ff3dff", "#ffee00", "#00ff7f", "#ff5d3a", "#8c9eff"];
            const groups = [...new Set(pts.map(p => p.group))];
            for (const g of groups) {
              const gp = pts.filter(p => p.group === g); ctx.strokeStyle = palette[g % palette.length]; ctx.fillStyle = ctx.strokeStyle; ctx.lineWidth = Math.max(2, canvas.width / 500);
              if (gp.length > 1) { ctx.beginPath(); ctx.moveTo(gp[0].x, gp[0].y); gp.slice(1).forEach(p => ctx.lineTo(p.x, p.y)); ctx.stroke(); }
              gp.forEach((p, i) => { ctx.beginPath(); ctx.arc(p.x, p.y, Math.max(4, canvas.width / 180), 0, 2*Math.PI); ctx.fill(); ctx.fillStyle = "white"; ctx.font = `${Math.max(12, canvas.width/70)}px sans-serif`; ctx.fillText(`${g}:${i+1}`, p.x + 6, p.y - 6); ctx.fillStyle = ctx.strokeStyle; });
            }
            const sp = model.get("alignment_points") || []; ctx.strokeStyle = "#ffffff"; ctx.fillStyle = "#ffffff"; ctx.lineWidth = Math.max(2, canvas.width/500);
            if (sp.length > 1) { ctx.beginPath(); ctx.moveTo(sp[0].x,sp[0].y); sp.slice(1).forEach(p => ctx.lineTo(p.x,p.y)); ctx.stroke(); }
            sp.forEach((p,i) => { ctx.beginPath(); ctx.arc(p.x,p.y,Math.max(5,canvas.width/160),0,2*Math.PI); ctx.fill(); ctx.fillText(`L${i+1}`,p.x+7,p.y+14); });
            status.textContent = ` ${pts.length} boundary points, ${sp.length} landmarks`;
          }
          function updateControls() {
            const boundaryMode = mode.value === "boundary";
            group.disabled = !boundaryMode; next.disabled = !boundaryMode;
            next.title = boundaryMode ? "Advance to the next wedge-boundary group" : "Landmarks are numbered automatically in click order";
          }
          img.onload = redraw; function loadImage() { img.src = model.get("image"); } loadImage(); updateControls();
          model.on("change:image", loadImage); model.on("change:points", redraw); model.on("change:alignment_points", redraw);
          canvas.addEventListener("click", ev => {
            const r = canvas.getBoundingClientRect(); const p = {x:(ev.clientX-r.left)*canvas.width/r.width, y:(ev.clientY-r.top)*canvas.height/r.height};
            if (mode.value === "alignment") model.set("alignment_points", [...(model.get("alignment_points")||[]), p]);
            else model.set("points", [...(model.get("points")||[]), {...p,group:Number(group.value)}]);
            model.save_changes(); redraw();
          });
          mode.onchange = () => { model.set("mode",mode.value); model.save_changes(); updateControls(); };
          group.onchange = () => { model.set("group",Number(group.value)); model.save_changes(); };
          next.onclick = () => { group.value=Number(group.value)+1; group.onchange(); };
          undo.onclick = () => { if (mode.value === "alignment") model.set("alignment_points",(model.get("alignment_points")||[]).slice(0,-1)); else model.set("points",(model.get("points")||[]).slice(0,-1)); model.save_changes(); redraw(); };
          reset.onclick = () => { if (mode.value === "alignment") model.set("alignment_points",[]); else model.set("points",[]); model.save_changes(); redraw(); };
        }
        export default { render };
        """
        _css = r"""
        .siemens-picker .toolbar { display:flex; gap:.45rem; align-items:center; flex-wrap:wrap; margin-bottom:.5rem; }
        .siemens-picker button, .siemens-picker select, .siemens-picker input { border:1px solid #8888; border-radius:5px; padding:.25rem .45rem; background:var(--marimo-background); color:inherit; }
        .siemens-picker input { width:4.5rem; }
        .siemens-picker canvas { display:block; width:100%; max-height:72vh; object-fit:contain; border:1px solid #8888; cursor:crosshair; background:#111; }
        .siemens-picker .status { opacity:.75; }
        """
        image = traitlets.Unicode().tag(sync=True)
        points = traitlets.List(default_value=[]).tag(sync=True)
        alignment_points = traitlets.List(default_value=[]).tag(sync=True)
        mode = traitlets.Unicode("boundary").tag(sync=True)
        group = traitlets.Int(0).tag(sync=True)

    def grouped_points(raw_points):
        _groups = {}
        for _point in raw_points:
            _groups.setdefault(int(_point["group"]), []).append([float(_point["x"]), float(_point["y"])])
        return {key: np.asarray(value, dtype=float) for key, value in _groups.items()}

    return PointPicker, grouped_points, image_to_data_url


@app.cell(hide_code=True)
def _(
    PointPicker,
    cv2,
    event_composite_rgb,
    image_to_data_url,
    mo,
    reference_bgr,
):
    if reference_bgr is not None and event_composite_rgb is not None:
        _reference_rgb = cv2.cvtColor(reference_bgr, cv2.COLOR_BGR2RGB)
        reference_picker = mo.ui.anywidget(PointPicker(image=image_to_data_url(_reference_rgb)))
        video_picker = mo.ui.anywidget(PointPicker(image=image_to_data_url(event_composite_rgb)))
        annotation_ui = mo.hstack([
            mo.vstack([
                mo.md("### Reference\nClick the chart center as L1, then square centers or matching corners clockwise. Landmarks are numbered automatically."),
                reference_picker,
            ]),
            mo.vstack([
                mo.md("### Event video\nClick the exact corresponding locations in the same order: L1→L1, L2→L2, and so on."),
                video_picker,
            ]),
        ], widths="equal")
    else:
        reference_picker = video_picker = None
        annotation_ui = mo.callout("Both a decoded video and reference image are required before annotation.", kind="info")
    mo.vstack([mo.md("## 3. Geometry annotation"), annotation_ui])
    return reference_picker, video_picker


@app.cell
def _(grouped_points, math, np):
    def fit_boundary_geometry(raw_points):
        _groups = grouped_points(raw_points)
        _lines, _residuals, _centroids = {}, {}, {}
        for _group, _points in _groups.items():
            if len(_points) < 2:
                continue
            _centroid = _points.mean(axis=0)
            _, _, _vh = np.linalg.svd(_points - _centroid, full_matrices=False)
            _direction = _vh[0]
            _normal = np.array([-_direction[1], _direction[0]])
            _normal /= np.linalg.norm(_normal)
            _line = np.r_[_normal, -np.dot(_normal, _centroid)]
            _lines[_group], _centroids[_group] = _line, _centroid
            _residuals[_group] = float(np.sqrt(np.mean(((_points @ _normal) + _line[2]) ** 2)))
        if len(_lines) < 2:
            return {"groups": _groups, "lines": _lines, "center": None, "residuals": _residuals, "angles": {}, "condition": float("inf")}
        _ids = sorted(_lines)
        _matrix = np.array([_lines[key][:2] for key in _ids])
        _rhs = -np.array([_lines[key][2] for key in _ids])
        _center, _, _, _singular = np.linalg.lstsq(_matrix, _rhs, rcond=None)
        _condition = float(_singular[0] / _singular[-1]) if len(_singular) > 1 and _singular[-1] > 1e-12 else float("inf")
        _angles = {key: math.atan2(*(_centroids[key] - _center)[::-1]) % (2 * math.pi) for key in _ids}
        return {"groups": _groups, "lines": _lines, "center": _center, "residuals": _residuals, "angles": _angles, "condition": _condition}

    def angle_between(a, b):
        return float(abs((b - a + math.pi) % (2 * math.pi) - math.pi))

    def boundary_gap_rows(reference_geometry, video_geometry):
        _common = sorted(set(reference_geometry["angles"]) & set(video_geometry["angles"]))
        if len(_common) < 2:
            return []
        _ordered = sorted(_common, key=lambda key: reference_geometry["angles"][key])
        _rows = []
        for _left, _right in zip(_ordered[:-1], _ordered[1:]):
            _rg = angle_between(reference_geometry["angles"][_left], reference_geometry["angles"][_right])
            _vg = angle_between(video_geometry["angles"][_left], video_geometry["angles"][_right])
            _rows.append({"left": _left, "right": _right, "reference_rad": _rg, "video_rad": _vg, "error_rad": _vg - _rg})
        return _rows

    return boundary_gap_rows, fit_boundary_geometry


@app.cell
def _(
    boundary_gap_rows,
    cv2,
    fit_boundary_geometry,
    math,
    np,
    reference_bgr,
    reference_picker,
    video_picker,
):
    _empty = {"groups": {}, "lines": {}, "center": None, "residuals": {}, "angles": {}, "condition": float("inf")}

    def fit_similarity(reference_landmarks, video_landmarks):
        if len(reference_landmarks) != len(video_landmarks) or len(reference_landmarks) < 3:
            return None
        _reference = np.array([[p["x"], p["y"]] for p in reference_landmarks], dtype=np.float32)
        _video = np.array([[p["x"], p["y"]] for p in video_landmarks], dtype=np.float32)
        _matrix, _inliers = cv2.estimateAffinePartial2D(
            _reference,
            _video,
            method=cv2.RANSAC,
            ransacReprojThreshold=4.0,
            maxIters=3000,
            confidence=0.995,
            refineIters=25,
        )
        if _matrix is None:
            return None
        _predicted = cv2.transform(_reference[None, :, :], _matrix)[0]
        _errors = np.linalg.norm(_predicted - _video, axis=1)
        _mask = _inliers.ravel().astype(bool) if _inliers is not None else np.ones(len(_errors), dtype=bool)
        _a, _b = float(_matrix[0, 0]), float(_matrix[0, 1])
        return {
            "matrix": _matrix,
            "scale": float(np.hypot(_a, _b)),
            "rotation_deg": float(np.degrees(np.arctan2(-_b, _a))),
            "rms_px": float(np.sqrt(np.mean(_errors[_mask] ** 2))),
            "max_error_px": float(np.max(_errors[_mask])),
            "inliers": int(_mask.sum()),
            "landmarks": len(_errors),
        }

    def transform_boundary_geometry(reference_geometry, matrix):
        _transformed = []
        for _group, _points in reference_geometry["groups"].items():
            _mapped = cv2.transform(_points.astype(np.float32)[None, :, :], matrix)[0]
            _transformed.extend(
                {"group": _group, "x": float(_point[0]), "y": float(_point[1])}
                for _point in _mapped
            )
        return fit_boundary_geometry(_transformed)

    def infer_reference_star(image_bgr, center):
        """Infer line-pair count and boundary phase from concentric rings."""
        if image_bgr is None or center is None:
            return None, None
        _height, _width = image_bgr.shape[:2]
        _cx, _cy = map(float, center)
        _maximum = min(_cx, _cy, _width - 1 - _cx, _height - 1 - _cy)
        if _maximum < 25:
            return None, None
        _gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
        _sample_count = 4096
        _angles = np.linspace(0, 2 * math.pi, _sample_count, endpoint=False)
        _spectra, _coefficients = [], []
        for _radius in np.linspace(0.45 * _maximum, 0.82 * _maximum, 8):
            _map_x = (_cx + _radius * np.cos(_angles)).astype(np.float32)[None, :]
            _map_y = (_cy + _radius * np.sin(_angles)).astype(np.float32)[None, :]
            _ring = cv2.remap(
                _gray,
                _map_x,
                _map_y,
                cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_REFLECT_101,
            )[0]
            _ring -= _ring.mean()
            _fft = np.fft.rfft(_ring)
            _magnitude = np.abs(_fft)
            _magnitude[:8] = 0
            _magnitude[513:] = 0
            _spectra.append(_magnitude / max(float(_magnitude.max()), 1e-9))
            _coefficients.append(_fft)
        _combined = np.mean(_spectra, axis=0)
        _cycles = int(np.argmax(_combined))
        if _cycles < 8:
            return None, None
        _ranked = np.sort(_combined[8:513])
        _confidence = float(_ranked[-1] / max(_ranked[-2], 1e-9))
        _unit_coefficients = [
            row[_cycles] / max(abs(row[_cycles]), 1e-9)
            for row in _coefficients
        ]
        _phase = float(np.angle(np.sum(_unit_coefficients)))
        _first_boundary = (math.pi / 2 - _phase) / _cycles
        _boundary_count = 2 * _cycles
        _raw_points = []
        for _group in range(_boundary_count):
            _angle = _first_boundary + _group * math.pi / _cycles
            for _radius in (0.30 * _maximum, 0.75 * _maximum):
                _raw_points.append({
                    "group": _group,
                    "x": _cx + _radius * math.cos(_angle),
                    "y": _cy + _radius * math.sin(_angle),
                })
        return fit_boundary_geometry(_raw_points), {
            "cycles_per_revolution": _cycles,
            "boundary_count": _boundary_count,
            "wedge_angle_deg": 180.0 / _cycles,
            "confidence_ratio": _confidence,
            "maximum_sample_radius_px": 0.82 * _maximum,
        }

    if reference_picker is not None and video_picker is not None:
        _reference_state = reference_picker.value
        _video_state = video_picker.value
        _reference_landmarks = _reference_state.get("alignment_points", [])
        _video_landmarks = _video_state.get("alignment_points", [])
        _manual_reference_geometry = fit_boundary_geometry(
            _reference_state.get("points", [])
        )
        manual_video_geometry = fit_boundary_geometry(_video_state.get("points", []))
        _center_landmark = (
            [_reference_landmarks[0]["x"], _reference_landmarks[0]["y"]]
            if _reference_landmarks
            else None
        )
        _automatic_geometry, star_detection = infer_reference_star(
            reference_bgr, _center_landmark
        )
        reference_geometry = (
            _manual_reference_geometry
            if len(_manual_reference_geometry["lines"]) >= 3
            else (_automatic_geometry or _manual_reference_geometry)
        )
        alignment = fit_similarity(_reference_landmarks, _video_landmarks)
        if alignment is not None and reference_geometry["lines"]:
            video_geometry = transform_boundary_geometry(reference_geometry, alignment["matrix"])
        else:
            video_geometry = manual_video_geometry
        _comparison_geometry = manual_video_geometry if len(manual_video_geometry["angles"]) >= 2 else video_geometry
        gap_rows = boundary_gap_rows(reference_geometry, _comparison_geometry)
    else:
        reference_geometry, manual_video_geometry, video_geometry = _empty, _empty.copy(), _empty.copy()
        alignment, gap_rows, star_detection = None, [], None
    return (
        alignment,
        gap_rows,
        reference_geometry,
        star_detection,
        video_geometry,
    )


@app.cell(hide_code=True)
def _(alignment, mo, reference_picker, star_detection, video_picker):
    if reference_picker is None or video_picker is None:
        _status = mo.callout("Upload both files to enable alignment.", kind="info")
    else:
        _reference_landmarks = reference_picker.value.get("alignment_points", [])
        _video_landmarks = video_picker.value.get("alignment_points", [])
        _reference_count = len(_reference_landmarks)
        _video_count = len(_video_landmarks)
        _rows = []
        for _index in range(max(_reference_count, _video_count)):
            _reference_point = _reference_landmarks[_index] if _index < _reference_count else None
            _video_point = _video_landmarks[_index] if _index < _video_count else None
            _rows.append({
                "Pair": f"L{_index + 1}",
                "Reference (x, y)": (
                    f"({_reference_point['x']:.1f}, {_reference_point['y']:.1f})"
                    if _reference_point else "missing"
                ),
                "Event video (x, y)": (
                    f"({_video_point['x']:.1f}, {_video_point['y']:.1f})"
                    if _video_point else "missing"
                ),
            })
        _messages = [
            f"Reference: **{_reference_count}** landmarks · Event video: **{_video_count}** landmarks."
        ]
        if star_detection is not None:
            _messages.append(
                f"Reference star: **{star_detection['cycles_per_revolution']} line pairs/revolution**, "
                f"**{star_detection['wedge_angle_deg']:.4g}°** per wedge."
            )
        if alignment is not None:
            _messages.append(
                f"Alignment ready — scale **{alignment['scale']:.6g}**, rotation "
                f"**{alignment['rotation_deg']:.4g}°**, RMS **{alignment['rms_px']:.3g} px**, "
                f"{alignment['inliers']}/{alignment['landmarks']} inliers."
            )
            _kind = "success"
        elif _reference_count != _video_count:
            _messages.append("Counts do not match. Undo the extra point or add its missing partner.")
            _kind = "warn"
        else:
            _messages.append("Select at least three one-to-one landmark pairs.")
            _kind = "info"
        _parts = [mo.callout(mo.md("\n\n".join(_messages)), kind=_kind, title="Live alignment status")]
        if _rows:
            _parts.append(mo.ui.table(_rows, selection=None, pagination=False, show_search=False))
        _status = mo.vstack(_parts)
    _status
    return


@app.cell(hide_code=True)
def _(mo):
    contrast_threshold = mo.ui.slider(0.05, 0.80, step=0.01, value=0.20, show_value=True, label="Normalized modulation cutoff")
    radial_bins = mo.ui.slider(50, 300, step=10, value=160, show_value=True, label="Radial samples")
    smoothing_bins = mo.ui.slider(1, 21, step=2, value=7, show_value=True, label="Smoothing bins")
    mo.vstack([mo.md("## 4. Resolution criterion"), mo.hstack([contrast_threshold, radial_bins, smoothing_bins], widths="equal")])
    return contrast_threshold, radial_bins, smoothing_bins


@app.cell
def _(math, np):
    def ordered_sector_angles(reference_geometry, video_geometry):
        _common = sorted(set(reference_geometry["angles"]) & set(video_geometry["angles"]))
        if len(_common) < 3:
            return []
        _order = sorted(_common, key=lambda key: reference_geometry["angles"][key])
        _result = []
        for _left, _right in zip(_order[:-1], _order[1:]):
            _a, _b = video_geometry["angles"][_left], video_geometry["angles"][_right]
            _signed = (_b - _a + math.pi) % (2 * math.pi) - math.pi
            if abs(_signed) <= math.radians(45):
                _result.append((_a, _a + _signed, _left, _right))
        return _result

    def contrast_profile(green_masks, orange_masks, center, sectors, number_of_radii, smoothing, threshold):
        if center is None or len(sectors) < 2 or green_masks.size == 0:
            return None
        _height, _width = green_masks.shape[1:]
        _corners = np.array([[0, 0], [_width - 1, 0], [0, _height - 1], [_width - 1, _height - 1]])
        _radii = np.linspace(2.0, float(np.max(np.linalg.norm(_corners - center, axis=1))), number_of_radii)
        _signed = green_masks.astype(np.int8) - orange_masks.astype(np.int8)
        _active = green_masks | orange_masks
        _contrast, _coverage = np.full(len(_radii), np.nan), np.zeros(len(_radii))
        for _ri, _radius in enumerate(_radii):
            _sector_samples, _sector_activity, _attempted, _inside = [], [], 0, 0
            for _a, _b, _, _ in sectors:
                _angles = np.linspace(_a, _b, 11)[1:-1]
                _values, _activities = [], []
                for _offset in [-1.5, 0.0, 1.5]:
                    _x = np.rint(center[0] + (_radius + _offset) * np.cos(_angles)).astype(int)
                    _y = np.rint(center[1] + (_radius + _offset) * np.sin(_angles)).astype(int)
                    _valid = (_x >= 0) & (_x < _width) & (_y >= 0) & (_y < _height)
                    _attempted += len(_angles); _inside += int(_valid.sum())
                    if np.any(_valid):
                        _values.append(_signed[:, _y[_valid], _x[_valid]].astype(float))
                        _activities.append(_active[:, _y[_valid], _x[_valid]].astype(float))
                if _values:
                    _sector_samples.append(np.concatenate(_values, axis=1).mean(axis=1))
                    _sector_activity.append(np.concatenate(_activities, axis=1).mean(axis=1))
            _coverage[_ri] = _inside / max(_attempted, 1)
            if len(_sector_samples) >= 2 and _coverage[_ri] >= 0.55:
                _values, _activities = np.stack(_sector_samples, axis=1), np.stack(_sector_activity, axis=1)
                _alternating = (-1.0) ** np.arange(_values.shape[1])
                _numerator = np.abs(np.sum(_values * _alternating, axis=1))
                _denominator = np.sum(_activities, axis=1)
                _usable = _denominator > 0
                if np.any(_usable):
                    _contrast[_ri] = float(np.sum(_numerator[_usable]) / np.sum(_denominator[_usable]))
        _valid_values = np.isfinite(_contrast)
        _kernel = np.ones(max(1, int(smoothing)), dtype=float)
        _num = np.convolve(np.nan_to_num(_contrast), _kernel, mode="same")
        _den = np.convolve(_valid_values.astype(float), _kernel, mode="same")
        _smooth = np.divide(_num, _den, out=np.full_like(_num, np.nan), where=_den > 0)
        _passing = np.isfinite(_smooth) & (_smooth >= threshold)
        _cutoff_index = next((_i for _i in range(max(0, len(_passing) - 2)) if np.all(_passing[_i:_i + 3])), None)
        return {"radii": _radii, "raw": _contrast, "smooth": _smooth, "coverage": _coverage, "cutoff_index": _cutoff_index, "cutoff_radius_px": float(_radii[_cutoff_index]) if _cutoff_index is not None else None}

    return contrast_profile, ordered_sector_angles


@app.cell
def _(
    alignment,
    contrast_profile,
    contrast_threshold,
    gap_rows,
    green_masks,
    np,
    orange_masks,
    ordered_sector_angles,
    radial_bins,
    reference_geometry,
    smoothing_bins,
    video_geometry,
):
    sectors = ordered_sector_angles(reference_geometry, video_geometry)
    radial_profile = contrast_profile(green_masks, orange_masks, video_geometry["center"], sectors, radial_bins.value, smoothing_bins.value, contrast_threshold.value)
    camera_px_per_reference_px = alignment["scale"] if alignment is not None else None
    nominal_wedge_angle_rad = float(np.median([row["reference_rad"] for row in gap_rows])) if gap_rows else None
    return camera_px_per_reference_px, nominal_wedge_angle_rad, radial_profile


@app.cell
def _(
    alignment,
    camera_pitch,
    camera_px_per_reference_px,
    contrast_threshold,
    gap_rows,
    math,
    monitor_height_px,
    monitor_pitch,
    monitor_width_px,
    nominal_wedge_angle_rad,
    np,
    radial_profile,
    reference_bgr,
    reference_file,
    reference_geometry,
    star_detection,
    video_file,
    video_geometry,
    video_metadata,
):
    result = None
    if radial_profile is not None and radial_profile["cutoff_radius_px"] is not None and nominal_wedge_angle_rad is not None:
        _radius_camera_px = radial_profile["cutoff_radius_px"]
        _camera_pitch_mm = camera_pitch.to("millimeter").magnitude
        _radius_sensor_mm = _radius_camera_px * _camera_pitch_mm
        _sensor_lp_per_mm = 1.0 / (2.0 * _radius_sensor_mm * nominal_wedge_angle_rad)
        _reference_radius_px = _display_lp_per_mm = _display_wedge_um = _fit_to_monitor = None
        if camera_px_per_reference_px and reference_bgr is not None:
            _reference_radius_px = _radius_camera_px / camera_px_per_reference_px
            _fit_to_monitor = min(monitor_width_px.value / reference_bgr.shape[1], monitor_height_px.value / reference_bgr.shape[0])
            _display_radius_mm = _reference_radius_px * _fit_to_monitor * monitor_pitch.to("millimeter").magnitude
            _display_lp_per_mm = 1.0 / (2.0 * _display_radius_mm * nominal_wedge_angle_rad)
            _display_wedge_um = _display_radius_mm * nominal_wedge_angle_rad * 1000.0
        _reference_gaps = np.array([row["reference_rad"] for row in gap_rows])
        _video_gaps = np.array([row["video_rad"] for row in gap_rows])
        result = {
            "video_filename": video_file.name() or "", "reference_filename": reference_file.name() or "", "sampled_frames": video_metadata.get("sampled_frames"),
            "wedge_angle_deg": math.degrees(nominal_wedge_angle_rad), "line_pair_angle_deg": 2 * math.degrees(nominal_wedge_angle_rad),
            "video_wedge_angle_deg": math.degrees(float(np.median(_video_gaps))), "angular_gap_mae_deg": math.degrees(float(np.mean(np.abs(_video_gaps - _reference_gaps)))),
            "cutoff_threshold": contrast_threshold.value, "cutoff_radius_camera_px": _radius_camera_px, "cutoff_radius_reference_px": _reference_radius_px,
            "camera_px_per_reference_px": camera_px_per_reference_px, "sensor_wedge_width_um": _radius_sensor_mm * nominal_wedge_angle_rad * 1000.0,
            "sensor_line_pairs_per_mm": _sensor_lp_per_mm, "sensor_nyquist_lp_per_mm": 1.0 / (2.0 * _camera_pitch_mm),
            "display_wedge_width_um": _display_wedge_um, "display_line_pairs_per_mm": _display_lp_per_mm,
            "monitor_um_per_px": monitor_pitch.magnitude, "camera_um_per_px": camera_pitch.magnitude, "reference_fit_scale": _fit_to_monitor,
            "reference_line_rms_px": float(np.mean(list(reference_geometry["residuals"].values()))) if reference_geometry["residuals"] else None,
            "video_line_rms_px": float(np.mean(list(video_geometry["residuals"].values()))) if video_geometry["residuals"] else None,
            "reference_center_condition": reference_geometry["condition"], "video_center_condition": video_geometry["condition"],
            "alignment_rotation_deg": alignment["rotation_deg"] if alignment else None,
            "alignment_rms_px": alignment["rms_px"] if alignment else None,
            "alignment_max_error_px": alignment["max_error_px"] if alignment else None,
            "alignment_inliers": alignment["inliers"] if alignment else None,
            "alignment_landmarks": alignment["landmarks"] if alignment else None,
            "star_line_pairs_per_revolution": star_detection["cycles_per_revolution"] if star_detection else None,
            "star_detection_confidence": star_detection["confidence_ratio"] if star_detection else None,
        }
    return (result,)


@app.cell
def _(np, plt):
    def annotation_overlay(image_rgb, geometry, title):
        _figure, _axis = plt.subplots(figsize=(8, 5))
        _axis.imshow(image_rgb); _axis.set_title(title); _axis.set_axis_off()
        _height, _width = image_rgb.shape[:2]
        for _group, _line in geometry["lines"].items():
            _a, _b, _c = _line
            if abs(_b) > abs(_a):
                _xs = np.array([0, _width - 1], dtype=float); _ys = -(_a * _xs + _c) / _b
            else:
                _ys = np.array([0, _height - 1], dtype=float); _xs = -(_b * _ys + _c) / _a
            _axis.plot(_xs, _ys, linewidth=1.2, label=f"boundary {_group}")
        for _points in geometry["groups"].values():
            _axis.scatter(_points[:, 0], _points[:, 1], s=18)
        if geometry["center"] is not None:
            _axis.scatter(*geometry["center"], marker="+", s=130, c="white", linewidths=2)
        _axis.set_xlim(0, _width); _axis.set_ylim(_height, 0)
        return _figure

    return (annotation_overlay,)


@app.cell(hide_code=True)
def _(
    alignment,
    annotation_overlay,
    contrast_threshold,
    cv2,
    event_composite_rgb,
    gap_rows,
    math,
    mo,
    plt,
    radial_profile,
    reference_bgr,
    reference_geometry,
    result,
    star_detection,
    video_geometry,
):
    _output = [mo.md("## 5. Results")]
    _problems = []
    if reference_geometry["center"] is None or video_geometry["center"] is None:
        _problems.append("Complete the paired landmark alignment. If automatic spoke detection fails, add three or more manual reference boundaries.")
    if len(gap_rows) < 2:
        _problems.append("No usable wedge geometry is available yet.")
    if star_detection is not None and star_detection["confidence_ratio"] < 1.15:
        _problems.append("Automatic spoke-count confidence is low; verify the reported line-pair count or supply manual reference boundaries.")
    if alignment is None:
        _problems.append("Add at least three matching center/alignment-square landmarks in both images.")
    elif alignment["rms_px"] > 4:
        _problems.append(f"Alignment RMS error is {alignment['rms_px']:.2f} px; review landmark order and placement.")
    if reference_geometry["condition"] > 100 or video_geometry["condition"] > 100:
        _problems.append("The fitted boundaries are nearly parallel. Use more widely separated visible boundaries.")
    if radial_profile is not None and radial_profile["cutoff_radius_px"] is None:
        _problems.append("No stable threshold crossing was found. Check masks and annotations, or adjust the threshold.")
    if _problems:
        _output.append(mo.callout(mo.md("\n".join(f"- {_p}" for _p in _problems)), kind="warn"))
    if reference_bgr is not None and event_composite_rgb is not None:
        _output.append(mo.hstack([
            annotation_overlay(cv2.cvtColor(reference_bgr, cv2.COLOR_BGR2RGB), reference_geometry, "Reference geometry"),
            annotation_overlay(event_composite_rgb, video_geometry, "Video geometry"),
        ], widths="equal"))
    if radial_profile is not None:
        _figure, _axis = plt.subplots(figsize=(10, 4))
        _axis.plot(radial_profile["radii"], radial_profile["raw"], alpha=0.35, label="raw")
        _axis.plot(radial_profile["radii"], radial_profile["smooth"], linewidth=2, label="smoothed")
        _axis.axhline(contrast_threshold.value, color="tab:red", linestyle="--", label="cutoff threshold")
        if radial_profile["cutoff_radius_px"] is not None:
            _axis.axvline(radial_profile["cutoff_radius_px"], color="tab:green", linestyle=":", label="limiting radius")
        _axis.set(xlabel="Radius from fitted center (camera px)", ylabel="Normalized alternating-wedge modulation", ylim=(0, 1.05))
        _axis.grid(alpha=0.2); _axis.legend(); _figure.tight_layout(); _output.append(_figure)
    if gap_rows:
        _output.append(mo.ui.table([{
            "Boundary pair": f"{_row['left']}–{_row['right']}", "Reference (deg)": round(math.degrees(_row["reference_rad"]), 5),
            "Observed/predicted (deg)": round(math.degrees(_row["video_rad"]), 5), "Error (deg)": round(math.degrees(_row["error_rad"]), 5),
        } for _row in gap_rows], selection=None, pagination=False))
    if result is not None:
        def _show(_value):
            return "—" if _value is None else f"{_value:.5g}"
        _summary = [
            {"Metric": "Wedge angular resolution", "Value": _show(result["wedge_angle_deg"]), "Unit": "deg"},
            {"Metric": "Line-pair angle", "Value": _show(result["line_pair_angle_deg"]), "Unit": "deg"},
            {"Metric": "Limiting camera radius", "Value": _show(result["cutoff_radius_camera_px"]), "Unit": "px"},
            {"Metric": "Sensor wedge width", "Value": _show(result["sensor_wedge_width_um"]), "Unit": "µm"},
            {"Metric": "Sensor spatial frequency", "Value": _show(result["sensor_line_pairs_per_mm"]), "Unit": "lp/mm"},
            {"Metric": "Sensor Nyquist", "Value": _show(result["sensor_nyquist_lp_per_mm"]), "Unit": "lp/mm"},
            {"Metric": "Display wedge width", "Value": _show(result["display_wedge_width_um"]), "Unit": "µm"},
            {"Metric": "Display spatial frequency", "Value": _show(result["display_line_pairs_per_mm"]), "Unit": "lp/mm"},
            {"Metric": "Reference→video scale", "Value": _show(result["camera_px_per_reference_px"]), "Unit": "camera px/reference px"},
            {"Metric": "Alignment rotation", "Value": _show(result["alignment_rotation_deg"]), "Unit": "deg"},
            {"Metric": "Alignment RMS", "Value": _show(result["alignment_rms_px"]), "Unit": "px"},
        ]
        _output.append(mo.ui.table(_summary, selection=None, pagination=False, show_search=False))
    _output.append(mo.md(r"Spatial frequency uses $f=1/(2r\,\Delta\theta)$, where $\Delta\theta$ is one wedge and two wedges form one line pair."))
    mo.vstack(_output)
    return


@app.cell(hide_code=True)
def _(csv, io, mo, result):
    if result is not None:
        _buffer = io.StringIO(); _writer = csv.DictWriter(_buffer, fieldnames=list(result)); _writer.writeheader(); _writer.writerow(result)
        _download = mo.download(_buffer.getvalue().encode("utf-8"), filename="siemens_resolution.csv", mimetype="text/csv", label="Download result CSV")
    else:
        _download = mo.download(b"", filename="siemens_resolution.csv", disabled=True, label="Download result CSV")
    _download
    return


@app.cell(hide_code=True)
def _(fit_boundary_geometry, math, np):
    _known_center = np.array([-120.0, 80.0])
    _synthetic = [{"group": _g, "x": _known_center[0] + _r * math.cos(_a), "y": _known_center[1] + _r * math.sin(_a)} for _g, _a in enumerate([0.08, 0.16, 0.24, 0.32]) for _r in [180.0, 260.0, 340.0]]
    _check = fit_boundary_geometry(_synthetic)
    assert np.linalg.norm(_check["center"] - _known_center) < 1e-7
    assert max(_check["residuals"].values()) < 1e-8
    return


if __name__ == "__main__":
    app.run()
