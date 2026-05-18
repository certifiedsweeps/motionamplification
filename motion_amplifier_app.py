"""
Eulerian Motion Amplifier — Streamlit Web App
Upload a short video clip, tune the sliders, amplify.

Deploy free: https://streamlit.io/cloud
Run locally:  streamlit run motion_amplifier_app.py
"""

import streamlit as st
import cv2
import numpy as np
import tempfile
import os
from pathlib import Path

# ─────────────────────────────────────────────
#  Page config
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Motion Amplifier",
    page_icon="🔬",
    layout="wide",
)

st.title("🔬 Eulerian Motion Amplifier")
st.caption(
    "Upload a short video. The app amplifies subtle motion in a chosen "
    "frequency band — making invisible vibrations, breathing, or structural "
    "flex clearly visible."
)

# ─────────────────────────────────────────────
#  Sidebar — controls
# ─────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Parameters")

    st.subheader("Frequency Band (Hz)")
    col1, col2 = st.columns(2)
    with col1:
        low_hz = st.number_input("Low", min_value=0.05, max_value=30.0,
                                  value=0.5, step=0.05, format="%.2f")
    with col2:
        high_hz = st.number_input("High", min_value=0.1, max_value=60.0,
                                   value=3.0, step=0.1, format="%.1f")
    if high_hz <= low_hz:
        st.warning("High must be greater than Low.")
        high_hz = low_hz + 0.1

    st.subheader("Amplification")
    amp_factor = st.slider("Amplify ×", min_value=1, max_value=200, value=20)

    st.subheader("Spatial Scale")
    pyr_level = st.slider(
        "Pyramid Level",
        min_value=0, max_value=4, value=3,
        help="Higher = coarser spatial blur. Motion at large scales is easier to amplify."
    )

    st.subheader("Video Options")
    max_frames = st.slider(
        "Max frames to process",
        min_value=30, max_value=600, value=150,
        help="Fewer frames = faster processing. 150 frames ≈ 5 sec at 30 fps."
    )
    output_fps = st.slider("Output FPS", min_value=10, max_value=60, value=30)

    st.divider()
    st.subheader("🎯 Frequency Cheat Sheet")
    st.markdown("""
| What to find | Low | High |
|---|---|---|
| Slow sway / breathing | 0.1 | 0.5 |
| Heart rate (face) | 0.8 | 2.0 |
| Speaking vibration | 2.0 | 6.0 |
| HVAC / fan | 10 | 30 |
| Structural resonance | 30 | 60 |
""")

# ─────────────────────────────────────────────
#  Core processing (same algorithm as CLI)
# ─────────────────────────────────────────────
def gaussian_pyramid(frame_f32, levels):
    pyr = [frame_f32]
    for _ in range(levels):
        pyr.append(cv2.pyrDown(pyr[-1]))
    return pyr


def process_video(frames, fps, low_hz, high_hz, amp, pyr_lvl, progress_bar):
    N  = len(frames)
    H, W = frames[0].shape[:2]
    levels = pyr_lvl + 1

    # ── Build pyramid buffer ──
    pyr_frames = []
    for i, f in enumerate(frames):
        pyr = gaussian_pyramid(f.astype(np.float32) / 255.0, levels)
        pyr_frames.append(pyr[pyr_lvl])
        if i % max(1, N // 20) == 0:
            progress_bar.progress(int(40 * i / N), text=f"Building pyramid… {i}/{N}")

    # ── FFT temporal filter ──
    progress_bar.progress(40, text="Running FFT temporal filter…")
    stacked      = np.stack(pyr_frames, axis=0)          # (N, h, w, C)
    fft          = np.fft.rfft(stacked, axis=0)
    freqs        = np.fft.rfftfreq(N, d=1.0 / fps)
    mask         = (freqs >= low_hz) & (freqs <= min(high_hz, fps / 2.0 - 0.01))
    filtered_fft = np.zeros_like(fft)
    filtered_fft[mask] = fft[mask]
    amplified    = np.fft.irfft(filtered_fft, n=N, axis=0)  # (N, h, w, C)
    progress_bar.progress(70, text="Compositing amplified frames…")

    # ── Composite ──
    results = []
    for i in range(N):
        amp_frame = amplified[i] * amp
        amp_up    = cv2.resize(amp_frame, (W, H), interpolation=cv2.INTER_LINEAR)
        base      = frames[i].astype(np.float32) / 255.0
        result    = np.clip(base + amp_up, 0.0, 1.0)
        results.append((result * 255.0).astype(np.uint8))
        if i % max(1, N // 10) == 0:
            progress_bar.progress(70 + int(25 * i / N), text=f"Compositing… {i}/{N}")

    progress_bar.progress(95, text="Encoding output video…")
    return results


def encode_video(frames, fps, path):
    h, w = frames[0].shape[:2]
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(path, fourcc, fps, (w, h))
    for f in frames:
        out.write(cv2.cvtColor(f, cv2.COLOR_RGB2BGR))
    out.release()


def read_video(path, max_frames):
    cap    = cv2.VideoCapture(path)
    fps    = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frames = []
    while len(frames) < max_frames:
        ret, frame = cap.read()
        if not ret:
            break
        frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    cap.release()
    return frames, fps


# ─────────────────────────────────────────────
#  Upload + Process
# ─────────────────────────────────────────────
uploaded = st.file_uploader(
    "Upload a video clip",
    type=["mp4", "mov", "avi", "mkv", "webm"],
    help="Short clips (5–15 sec) work best. Longer clips are trimmed to Max Frames."
)

if uploaded:
    # Save upload to temp file
    suffix = Path(uploaded.name).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_in:
        tmp_in.write(uploaded.read())
        input_path = tmp_in.name

    # Preview original
    st.subheader("📹 Original")
    st.video(input_path)

    st.divider()

    if st.button("🚀 Amplify Motion", type="primary", use_container_width=True):
        progress = st.progress(0, text="Reading video…")

        frames, source_fps = read_video(input_path, max_frames)
        if not frames:
            st.error("Could not read any frames from the video.")
            st.stop()

        n_frames = len(frames)
        h, w     = frames[0].shape[:2]
        duration = n_frames / source_fps

        progress.progress(10, text=f"Loaded {n_frames} frames  ({w}×{h}, {source_fps:.0f} fps, {duration:.1f}s)")

        if n_frames < 8:
            st.warning("Clip is very short. Use at least 1–2 seconds for meaningful results.")

        nyquist = source_fps / 2.0
        if high_hz >= nyquist:
            st.warning(f"High Hz ({high_hz}) is above Nyquist ({nyquist:.1f} Hz) "
                       f"for this video's frame rate. It will be clamped automatically.")

        # Process
        result_frames = process_video(
            frames, source_fps, low_hz, high_hz, amp_factor, pyr_level, progress
        )

        # Encode
        tmp_out = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        tmp_out.close()
        encode_video(result_frames, output_fps, tmp_out.name)

        progress.progress(100, text="Done!")

        # Show result
        st.subheader("✨ Amplified Output")
        st.video(tmp_out.name)

        # Side-by-side first frames
        st.subheader("🔍 Frame Comparison (first frame)")
        c1, c2 = st.columns(2)
        c1.image(frames[0],         caption="Original",   use_container_width=True)
        c2.image(result_frames[0],  caption="Amplified",  use_container_width=True)

        # Download
        with open(tmp_out.name, "rb") as f:
            st.download_button(
                label="⬇️ Download Amplified Video",
                data=f,
                file_name="amplified_output.mp4",
                mime="video/mp4",
                use_container_width=True,
            )

        # Stats
        with st.expander("📊 Processing details"):
            st.markdown(f"""
| Parameter | Value |
|---|---|
| Frames processed | {n_frames} |
| Source FPS | {source_fps:.1f} |
| Resolution | {w} × {h} |
| Duration | {duration:.2f} s |
| Frequency band | {low_hz:.2f} – {high_hz:.2f} Hz |
| Amplification | {amp_factor}× |
| Pyramid level | {pyr_level} |
| Freq. resolution | {source_fps / n_frames:.3f} Hz/bin |
""")

        # Cleanup
        os.unlink(tmp_out.name)

    os.unlink(input_path)

else:
    st.info("👆 Upload a video to get started. Short, stable clips (camera on a tripod or flat surface) give the best results.")

    with st.expander("💡 Tips for good results"):
        st.markdown("""
- **Stabilise the camera.** Set it on a table, tripod, or lean it against something solid.
  Camera shake drowns the signal.
- **Start with Amplify at 20–50**, then go higher once you've found the right frequency.
- **Pyramid Level 3–4** works well for most subjects. Drop to 0–1 if you want
  fine spatial detail in the amplification.
- **Sweep the frequency band.** Try several Low/High combos and re-process.
- Heart rate in a face: `Low 0.8 / High 2.0 / Amp 50–100`.
- Structural vibration: `Low 10 / High 30 / Amp 20–40`.
""")
