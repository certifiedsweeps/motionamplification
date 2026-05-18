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

# Longest edge is capped to this before any processing.
# Keeps peak RAM well under 500 MB even at 150 frames.
MAX_DIM = 480

st.set_page_config(page_title="Motion Amplifier", page_icon="🔬", layout="wide")

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
    amp_factor = st.slider("Amplify x", min_value=1, max_value=200, value=20)

    st.subheader("Spatial Scale")
    pyr_level = st.slider(
        "Pyramid Level", min_value=0, max_value=4, value=3,
        help="Higher = coarser spatial blur. Usually 3-4 works best."
    )

    st.subheader("Video Options")
    max_frames = st.slider(
        "Max frames to process", min_value=30, max_value=300, value=90,
        help="90 frames = ~3 sec at 30 fps. More frames = finer frequency resolution."
    )
    output_fps = st.slider("Output FPS", min_value=10, max_value=60, value=30)

    st.divider()
    st.subheader("Frequency Cheat Sheet")
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
#  Core processing
# ─────────────────────────────────────────────
def gaussian_pyramid(frame_f32, levels):
    pyr = [frame_f32]
    for _ in range(levels):
        pyr.append(cv2.pyrDown(pyr[-1]))
    return pyr


def read_video(path, max_frames):
    """Read up to max_frames, downscaling so longest edge <= MAX_DIM."""
    cap   = cv2.VideoCapture(path)
    fps   = cap.get(cv2.CAP_PROP_FPS) or 30.0
    src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    scale = min(1.0, MAX_DIM / max(src_w, src_h, 1))
    dst_w = max(2, int(src_w * scale) & ~1)   # keep even for codec
    dst_h = max(2, int(src_h * scale) & ~1)

    frames = []
    while len(frames) < max_frames:
        ret, frame = cap.read()
        if not ret:
            break
        if scale < 1.0:
            frame = cv2.resize(frame, (dst_w, dst_h), interpolation=cv2.INTER_AREA)
        frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

    cap.release()
    return frames, fps, src_w, src_h, scale


def process_video(frames, fps, low_hz, high_hz, amp, pyr_lvl, progress_bar):
    N = len(frames)
    H, W = frames[0].shape[:2]

    # Build pyramid-level buffer
    pyr_frames = []
    for i, f in enumerate(frames):
        pyr = gaussian_pyramid(f.astype(np.float32) / 255.0, pyr_lvl + 1)
        pyr_frames.append(pyr[pyr_lvl])
        if i % max(1, N // 20) == 0:
            progress_bar.progress(int(40 * i / N), text=f"Building pyramid... {i}/{N}")

    # FFT temporal bandpass
    progress_bar.progress(40, text="Running FFT temporal filter...")
    stacked      = np.stack(pyr_frames, axis=0)
    del pyr_frames
    fft          = np.fft.rfft(stacked, axis=0)
    del stacked
    freqs        = np.fft.rfftfreq(N, d=1.0 / fps)
    mask         = (freqs >= low_hz) & (freqs <= min(high_hz, fps / 2.0 - 0.01))
    filtered_fft = np.zeros_like(fft)
    filtered_fft[mask] = fft[mask]
    del fft
    amplified = np.fft.irfft(filtered_fft, n=N, axis=0)
    del filtered_fft
    progress_bar.progress(70, text="Compositing amplified frames...")

    # Composite: original + amplified motion
    results = []
    for i in range(N):
        amp_up = cv2.resize(amplified[i] * amp, (W, H), interpolation=cv2.INTER_LINEAR)
        result = np.clip(frames[i].astype(np.float32) / 255.0 + amp_up, 0.0, 1.0)
        results.append((result * 255.0).astype(np.uint8))
        if i % max(1, N // 10) == 0:
            progress_bar.progress(70 + int(25 * i / N), text=f"Compositing... {i}/{N}")

    del amplified
    progress_bar.progress(95, text="Encoding output video...")
    return results


def encode_video(frames, fps, path):
    h, w   = frames[0].shape[:2]
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out    = cv2.VideoWriter(path, fourcc, fps, (w, h))
    for f in frames:
        out.write(cv2.cvtColor(f, cv2.COLOR_RGB2BGR))
    out.release()


# ─────────────────────────────────────────────
#  Upload + Process
# ─────────────────────────────────────────────
uploaded = st.file_uploader(
    "Upload a video clip",
    type=["mp4", "mov", "avi", "mkv", "webm"],
    help="Short clips (3-10 sec) work best. Longer clips are trimmed to Max Frames."
)

if uploaded:
    suffix = Path(uploaded.name).suffix or ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_in:
        tmp_in.write(uploaded.read())
        input_path = tmp_in.name

    st.subheader("Original")
    st.video(input_path)
    st.divider()

    if st.button("Amplify Motion", type="primary", use_container_width=True):
        try:
            progress = st.progress(0, text="Reading video...")

            frames, source_fps, src_w, src_h, scale = read_video(input_path, max_frames)

            if not frames:
                st.error("Could not read any frames. Try a different video format.")
                st.stop()

            n_frames       = len(frames)
            proc_h, proc_w = frames[0].shape[:2]
            duration       = n_frames / source_fps

            scale_note = f" (downscaled from {src_w}x{src_h})" if scale < 1.0 else ""
            progress.progress(10, text=(
                f"Loaded {n_frames} frames - "
                f"{proc_w}x{proc_h}{scale_note}, "
                f"{source_fps:.0f} fps, {duration:.1f}s"
            ))

            if n_frames < 8:
                st.warning("Very short clip - use at least 1-2 seconds for meaningful results.")

            nyquist = source_fps / 2.0
            if high_hz >= nyquist:
                st.warning(
                    f"High Hz ({high_hz}) is above the Nyquist limit "
                    f"({nyquist:.1f} Hz) for this video's frame rate - it will be clamped."
                )

            result_frames = process_video(
                frames, source_fps, low_hz, high_hz,
                amp_factor, pyr_level, progress
            )

            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_out:
                out_path = tmp_out.name
            encode_video(result_frames, output_fps, out_path)

            progress.progress(100, text="Done!")

            st.subheader("Amplified Output")
            st.video(out_path)

            st.subheader("Frame Comparison (first frame)")
            c1, c2 = st.columns(2)
            c1.image(frames[0],        caption="Original",  use_container_width=True)
            c2.image(result_frames[0], caption="Amplified", use_container_width=True)

            with open(out_path, "rb") as f:
                st.download_button(
                    label="Download Amplified Video",
                    data=f,
                    file_name="amplified_output.mp4",
                    mime="video/mp4",
                    use_container_width=True,
                )

            with st.expander("Processing details"):
                st.markdown(f"""
| Parameter | Value |
|---|---|
| Frames processed | {n_frames} |
| Source FPS | {source_fps:.1f} |
| Processing resolution | {proc_w} x {proc_h} |
| Original resolution | {src_w} x {src_h} |
| Duration | {duration:.2f} s |
| Frequency band | {low_hz:.2f} - {high_hz:.2f} Hz |
| Amplification | {amp_factor}x |
| Pyramid level | {pyr_level} |
| Freq. resolution | {source_fps / n_frames:.3f} Hz/bin |
""")
            os.unlink(out_path)

        except MemoryError:
            st.error(
                "Ran out of memory. Try reducing Max Frames in the sidebar, "
                "or use a shorter / lower-resolution clip."
            )
        except Exception as e:
            st.error(f"Processing failed: {e}")

    os.unlink(input_path)

else:
    st.info("Upload a video to get started. Short, stable clips give the best results.")

    with st.expander("Tips for good results"):
        st.markdown("""
- **Stabilise the camera.** Set it on a table or tripod - camera shake drowns the signal.
- **Start with Amplify 20-50**, then go higher once you've found the right frequency.
- **Pyramid Level 3-4** works well for most subjects.
- **Sweep the frequency band.** Try several Low/High combos and re-process.
- Heart rate in a face: `Low 0.8 / High 2.0 / Amp 50-100`
- Structural vibration: `Low 10 / High 30 / Amp 20-40`
""")
