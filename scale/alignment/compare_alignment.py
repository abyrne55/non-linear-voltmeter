#!/usr/bin/env python3
"""Perspective-correct reference.jpg onto the generated Cricut faceplate
and produce alignment overlays (debug, warped, overlay, edges, crops)
plus dimensional measurements. Outputs go to scale/reference_*.png."""

import numpy as np
from PIL import Image
from scipy import ndimage
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# ── Physical constants (from meter_scale_cricut.py) ──────────────────
PLATE_W = 60.0        # mm
PLATE_H = 35.7        # mm
PX_MM   = 20.0        # generated PNG: 508 DPI / 25.4
GEN_W   = 1200        # px
GEN_H   = 714         # px

HOLE_X  = 14.0        # mm from side edge
HOLE_Y  = 3.0         # mm from bottom edge
HOLE_DIA = 2.5        # mm
HOLE_SPACING = PLATE_W - 2 * HOLE_X  # 32 mm

NOTCH_W = 22.7        # mm
NOTCH_H = 5.85        # mm
ARC_R   = 31.5        # mm
SWEEP   = 90.0        # degrees
PIVOT_FROM_TOP = 39.2  # mm

# Derived pixel coordinates in generated-PNG space (y=0 at top)
HOLE_L = np.array([HOLE_X * PX_MM, GEN_H - HOLE_Y * PX_MM])
HOLE_R = np.array([(PLATE_W - HOLE_X) * PX_MM, GEN_H - HOLE_Y * PX_MM])
PIVOT  = np.array([PLATE_W / 2 * PX_MM, PIVOT_FROM_TOP * PX_MM])
ARC_R_PX = ARC_R * PX_MM

DIR = Path(__file__).parent
GEN_PATH  = DIR.parent / 'meter_scale_cricut_6x3.57cm.png'
IMG_PATH  = DIR / 'reference.jpg'

# Hand-verified plate corners for reference (iteratively corrected)
reference_CORNERS = {
    'tl': np.array([425.0, 808.0]),
    'tr': np.array([2548.0, 819.0]),
    'bl': np.array([416.0, 2071.0]),
    'br': np.array([2540.0, 2088.0]),
}


# ═════════════════════════════════════════════════════════════════════
# Image utilities
# ═════════════════════════════════════════════════════════════════════

def to_gray(rgb):
    return np.mean(rgb[:, :, :3].astype(np.float64), axis=2)


def gen_on_white(gen_rgba):
    a = gen_rgba[:, :, 3:4].astype(np.float64) / 255.0
    rgb = gen_rgba[:, :, :3].astype(np.float64)
    return np.clip(255.0 * (1 - a) + rgb * a, 0, 255).astype(np.uint8)


# ═════════════════════════════════════════════════════════════════════
# Detection
# ═════════════════════════════════════════════════════════════════════

def find_hole_centroid(gray, cx_est, cy_est, search_r=80):
    """Darkness-weighted centroid of a screw hole near (cx_est, cy_est)."""
    h, w = gray.shape
    y0 = max(0, int(cy_est - search_r))
    y1 = min(h, int(cy_est + search_r))
    x0 = max(0, int(cx_est - search_r))
    x1 = min(w, int(cx_est + search_r))
    crop = gray[y0:y1, x0:x1]

    med = np.median(crop)
    thresh = med * 0.75
    mask = crop < thresh
    if mask.sum() < 10:
        thresh = med * 0.90
        mask = crop < thresh
        if mask.sum() < 10:
            return None

    yy, xx = np.mgrid[0:crop.shape[0], 0:crop.shape[1]]
    weights = np.where(mask, thresh - crop, 0).astype(np.float64)
    total = weights.sum()
    if total < 1:
        return None
    return np.array([x0 + (xx * weights).sum() / total,
                     y0 + (yy * weights).sum() / total])



def detect_plate(img_rgb):
    """Segment meter plate from pink fabric background."""
    r = img_rgb[:, :, 0].astype(np.float64)
    g = img_rgb[:, :, 1].astype(np.float64)
    b = img_rgb[:, :, 2].astype(np.float64)

    pinkness = r - (g + b) / 2.0
    brightness = (r + g + b) / 3.0
    mask = (pinkness < 10) & (brightness > 100)

    mask = ndimage.binary_closing(mask, structure=np.ones((25, 25)))
    mask = ndimage.binary_fill_holes(mask)
    mask = ndimage.binary_opening(mask, structure=np.ones((10, 10)))

    labeled, n = ndimage.label(mask)
    if n == 0:
        return None, None
    sizes = ndimage.sum(mask, labeled, range(1, n + 1))
    plate = (labeled == (np.argmax(sizes) + 1))

    rows = np.where(np.any(plate, axis=1))[0]
    cols = np.where(np.any(plate, axis=0))[0]
    y_min, y_max = rows[0], rows[-1]
    x_min, x_max = cols[0], cols[-1]

    top_band = plate[y_min:y_min + 50, :]
    top_cols = np.where(np.any(top_band, axis=0))[0]
    tl = np.array([float(top_cols[0]), float(y_min)])
    tr = np.array([float(top_cols[-1]), float(y_min)])

    return plate, {
        'tl': tl, 'tr': tr,
        'bbox': (y_min, y_max, x_min, x_max),
    }


def detect_holes(gray, corners):
    tl, tr = corners['tl'], corners['tr']
    y_max = corners['bbox'][1]
    plate_w = tr[0] - tl[0]
    px_mm = plate_w / PLATE_W

    lx = tl[0] + HOLE_X * px_mm
    rx = tl[0] + (PLATE_W - HOLE_X) * px_mm
    by = tl[1] + (PLATE_H - HOLE_Y) * px_mm
    sr = int(2 * px_mm)

    hl = find_hole_centroid(gray, lx, by, search_r=sr)
    hr = find_hole_centroid(gray, rx, by, search_r=sr)
    return hl, hr


# ═════════════════════════════════════════════════════════════════════
# Transforms
# ═════════════════════════════════════════════════════════════════════


def homography_dlt(src_pts, dst_pts):
    """3×3 homography via Direct Linear Transform from ≥4 point pairs."""
    A = []
    for (sx, sy), (dx, dy) in zip(src_pts, dst_pts):
        A.append([-sx, -sy, -1, 0, 0, 0, dx * sx, dx * sy, dx])
        A.append([0, 0, 0, -sx, -sy, -1, dy * sx, dy * sy, dy])
    _, _, Vt = np.linalg.svd(np.array(A, dtype=np.float64))
    H = Vt[-1].reshape(3, 3)
    return H / H[2, 2]


def warp(img, H_fwd, out_shape):
    """Warp image using forward homography (source→dest)."""
    H_inv = np.linalg.inv(H_fwd)
    oh, ow = out_shape[:2]
    yy, xx = np.mgrid[0:oh, 0:ow].astype(np.float64)
    coords = np.stack([xx.ravel(), yy.ravel(), np.ones(oh * ow)])
    src = H_inv @ coords
    src_x = (src[0] / src[2]).reshape(oh, ow)
    src_y = (src[1] / src[2]).reshape(oh, ow)

    if img.ndim == 2:
        return np.clip(
            ndimage.map_coordinates(img.astype(np.float64), [src_y, src_x],
                                    order=1, mode='constant', cval=0),
            0, 255).astype(np.uint8)
    out = np.zeros((oh, ow, img.shape[2]), dtype=np.uint8)
    for c in range(img.shape[2]):
        out[:, :, c] = np.clip(
            ndimage.map_coordinates(img[:, :, c].astype(np.float64),
                                    [src_y, src_x], order=1, mode='constant', cval=0),
            0, 255).astype(np.uint8)
    return out


# ═════════════════════════════════════════════════════════════════════
# Output generation
# ═════════════════════════════════════════════════════════════════════

def save_debug(img_rgb, features, path, title, px_mm=None):
    """Annotate original image with detected feature locations."""
    ar = img_rgb.shape[0] / img_rgb.shape[1]
    fig, ax = plt.subplots(figsize=(12, 12 * ar))
    ax.imshow(img_rgb)

    if px_mm is None:
        px_mm = img_rgb.shape[1] / PLATE_W

    colors = {'hole_L': 'lime', 'hole_R': 'lime',
              'tl': 'red', 'tr': 'red', 'bl': 'orange', 'br': 'orange'}

    for name, val in features.items():
        if val is None or name == 'bbox':
            continue
        pt = val
        col = colors.get(name, 'cyan')
        r = HOLE_DIA / 2 * px_mm if 'hole' in name else 12
        ax.add_patch(plt.Circle((pt[0], pt[1]), r, fill=False, ec=col, lw=0.8))
        ax.plot([pt[0] - r, pt[0] + r], [pt[1], pt[1]], color=col, lw=0.6)
        ax.plot([pt[0], pt[0]], [pt[1] - r, pt[1] + r], color=col, lw=0.6)
        ax.annotate(name, (pt[0], pt[1]), textcoords='offset points',
                    xytext=(12, 12), fontsize=9, color=col, fontweight='bold',
                    bbox=dict(boxstyle='round,pad=0.2', fc='black', alpha=0.7))

    ax.set_title(title, fontsize=11)
    ax.axis('off')
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f'  {path.name}')


def save_overlay(warped_rgb, gen_rgba, path):
    """50% opacity composite of generated PNG over warped photo."""
    a = gen_rgba[:, :, 3:4].astype(np.float64) / 255.0 * 0.5
    blended = warped_rgb.astype(np.float64) * (1 - a) + \
              gen_rgba[:, :, :3].astype(np.float64) * a
    Image.fromarray(np.clip(blended, 0, 255).astype(np.uint8)).save(path)
    print(f'  {path.name}')


def save_edges(warped_gray, gen_gray, path):
    """Edge overlay: red = generated edges, cyan = photo edges."""
    def sobel_mag(g):
        sx = ndimage.sobel(g.astype(np.float64), axis=1)
        sy = ndimage.sobel(g.astype(np.float64), axis=0)
        mag = np.hypot(sx, sy)
        mx = mag.max()
        return np.clip(mag / mx * 255, 0, 255) if mx > 0 else mag

    eg = sobel_mag(gen_gray)
    ep = sobel_mag(warped_gray)
    eg = np.where(eg > 25, eg, 0)
    ep = np.where(ep > 25, ep, 0)

    canvas = np.full((*warped_gray.shape, 3), 32, dtype=np.uint8)
    canvas[:, :, 0] = np.clip(32 + eg, 0, 255).astype(np.uint8)   # red
    canvas[:, :, 1] = np.clip(32 + ep, 0, 255).astype(np.uint8)   # green
    canvas[:, :, 2] = np.clip(32 + ep, 0, 255).astype(np.uint8)   # blue → cyan
    Image.fromarray(canvas).save(path)
    print(f'  {path.name}')


def save_crops(warped_rgb, gen_rgba, prefix):
    """Feature zoom crops: holes, cutout, arc endpoints."""
    a = gen_rgba[:, :, 3:4].astype(np.float64) / 255.0 * 0.5
    blended = np.clip(
        warped_rgb.astype(np.float64) * (1 - a) +
        gen_rgba[:, :, :3].astype(np.float64) * a,
        0, 255).astype(np.uint8)

    h, w = blended.shape[:2]

    def box(cx, cy, r=100):
        cx, cy = int(cx), int(cy)
        return blended[max(0, cy-r):min(h, cy+r), max(0, cx-r):min(w, cx+r)]

    crops = [
        (box(*HOLE_L), 'Left hole'),
        (box(*HOLE_R), 'Right hole'),
    ]

    # Cutout — wider crop
    nw = int(NOTCH_W * PX_MM * 0.7)
    nh = int(NOTCH_H * PX_MM * 1.5)
    ncx, ncy = int(GEN_W / 2), int(GEN_H - NOTCH_H / 2 * PX_MM)
    crops.append((blended[max(0, ncy-nh):min(h, ncy+nh),
                          max(0, ncx-nw):min(w, ncx+nw)], 'Cutout'))

    # Arc endpoints (pivot is below image; arc at 135° and 45°)
    for label, deg in [('Arc 0V', 135), ('Arc max', 45)]:
        ax_ = PIVOT[0] + ARC_R_PX * np.cos(np.radians(deg))
        ay_ = PIVOT[1] - ARC_R_PX * np.sin(np.radians(deg))
        crops.append((box(ax_, ay_), label))

    fig, axes = plt.subplots(1, len(crops), figsize=(4 * len(crops), 4))
    for ax, (img, label) in zip(axes, crops):
        ax.imshow(img)
        ax.set_title(label, fontsize=10)
        ax.axis('off')
    fig.tight_layout()
    path = prefix.parent / f'{prefix.name}_crops.png'
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f'  {path.name}')


# ═════════════════════════════════════════════════════════════════════
# Measurements
# ═════════════════════════════════════════════════════════════════════

def measure_notch(warped_rgb):
    """Measure notch width/height using pinkness gradient edge detection."""
    r = warped_rgb[:, :, 0].astype(np.float64)
    g = warped_rgb[:, :, 1].astype(np.float64)
    b = warped_rgb[:, :, 2].astype(np.float64)
    pinkness = r - (g + b) / 2.0

    widths = []
    cx0 = int(GEN_W * 0.25)
    cx1 = int(GEN_W * 0.75)
    for y_off_mm in [1.0, 1.5, 2.0, 2.5]:
        y = int(GEN_H - y_off_mm * PX_MM)
        if y < 0 or y >= GEN_H:
            continue
        grad = np.gradient(pinkness[y, :])
        cg = grad[cx0:cx1]
        pos_idx = np.argmax(cg)
        neg_idx = np.argmin(cg)
        if cg[pos_idx] > 8 and cg[neg_idx] < -8 and pos_idx < neg_idx:
            w = (neg_idx - pos_idx) / PX_MM
            if 10 < w < 40:
                widths.append(w)

    if not widths:
        return None, None
    notch_w = np.median(widths)

    cx = GEN_W // 2
    notch_h = None
    for y in range(GEN_H - int(0.5 * PX_MM), max(0, GEN_H - int(10 * PX_MM)), -1):
        if pinkness[y, cx] < 10:
            notch_h = (GEN_H - y) / PX_MM
            break

    return notch_w, notch_h


def measure_arc(warped_gray):
    """Find arc radius and angular extent by searching multiple radii."""
    angles = np.linspace(35, 145, 400)
    plate_region = warped_gray[int(GEN_H * 0.4):int(GEN_H * 0.55),
                               int(GEN_W * 0.35):int(GEN_W * 0.65)]
    plate_val = np.median(plate_region)
    thresh = plate_val * 0.6

    best_radius = None
    best_count = 0
    for r_px in range(int(ARC_R_PX - 60), int(ARC_R_PX + 81), 4):
        count = 0
        for deg in angles:
            rad = np.radians(deg)
            x = int(round(PIVOT[0] + r_px * np.cos(rad)))
            y = int(round(PIVOT[1] - r_px * np.sin(rad)))
            if 0 <= x < GEN_W and 0 <= y < GEN_H:
                if warped_gray[y, x] < thresh:
                    count += 1
        if count > best_count:
            best_count = count
            best_radius = r_px

    if best_radius is None or best_count < 20:
        return None, None, None

    vals = np.full(len(angles), 255.0)
    for i, deg in enumerate(angles):
        rad = np.radians(deg)
        x = int(round(PIVOT[0] + best_radius * np.cos(rad)))
        y = int(round(PIVOT[1] - best_radius * np.sin(rad)))
        if 0 <= x < GEN_W and 0 <= y < GEN_H:
            y0, y1 = max(0, y - 2), min(GEN_H, y + 3)
            x0, x1 = max(0, x - 2), min(GEN_W, x + 3)
            vals[i] = warped_gray[y0:y1, x0:x1].mean()

    dark = vals < thresh
    if not dark.any():
        return None, None, None
    arc_degs = angles[dark]
    return arc_degs[0], arc_degs[-1], best_radius / PX_MM


def print_measurements(name, hole_l, hole_r, plate_w_px, plate_h_px,
                       bottom_y, warped_rgb, warped_gray):
    print(f'\n  {name}:')
    if hole_l is None or hole_r is None:
        print('    [holes not detected]')
        return

    if plate_w_px:
        px_mm_x = plate_w_px / PLATE_W
    else:
        px_mm_x = np.linalg.norm(hole_r - hole_l) / HOLE_SPACING
    px_mm_y = plate_h_px / PLATE_H if plate_h_px else px_mm_x
    px_mm = np.sqrt(px_mm_x * px_mm_y)

    hole_dist = np.linalg.norm(hole_r - hole_l) / px_mm
    print(f'    Hole spacing:       {hole_dist:6.2f} mm  (expected {HOLE_SPACING:.1f})')

    if bottom_y is not None:
        hole_y_avg = (hole_l[1] + hole_r[1]) / 2.0
        from_bot = (bottom_y - hole_y_avg) / px_mm_y
        print(f'    Hole from bottom:   {from_bot:6.2f} mm  (expected {HOLE_Y:.1f})')

    tilt = np.degrees(np.arctan2(hole_r[1] - hole_l[1], hole_r[0] - hole_l[0]))
    print(f'    Plate tilt:         {tilt:+.3f}°')

    if warped_rgb is not None:
        nw, nh = measure_notch(warped_rgb)
        if nw is not None:
            print(f'    Notch width:        {nw:6.2f} mm  (expected {NOTCH_W:.1f})')
        if nh is not None:
            print(f'    Notch height:       {nh:6.2f} mm  (expected {NOTCH_H:.1f})')

    if warped_gray is not None:
        a0, a1, arc_r = measure_arc(warped_gray)
        if a0 is not None:
            print(f'    Arc endpoints:      {a0:.1f}° .. {a1:.1f}°  (expected 45.0° .. 135.0°)')
            print(f'    Arc sweep:          {a1 - a0:.1f}°  (expected {SWEEP:.1f}°)')
            print(f'    Arc radius:         {arc_r:6.2f} mm  (expected {ARC_R:.1f})')


# ═════════════════════════════════════════════════════════════════════
# Main
# ═════════════════════════════════════════════════════════════════════

def main():
    for p in [GEN_PATH, IMG_PATH]:
        if not p.exists():
            print(f'ERROR: {p} not found')
            return 1

    print('Loading images...')
    gen_rgba = np.array(Image.open(GEN_PATH))
    img_ref = np.array(Image.open(IMG_PATH))
    gen_gray = to_gray(gen_on_white(gen_rgba))

    # ── reference ─────────────────────────────────────────────────────
    print('\n=== reference ===')
    gray_ref = to_gray(img_ref)
    corners = reference_CORNERS
    tl = corners['tl']
    tr = corners['tr']
    bl = corners['bl']
    br = corners['br']
    y_min = min(tl[1], tr[1])
    y_max = max(bl[1], br[1])
    x_min = min(tl[0], bl[0])
    x_max = max(tr[0], br[0])
    bbox = (int(y_min), int(y_max), int(x_min), int(x_max))
    plate_w_px = tr[0] - tl[0]
    plate_h_px = float(y_max - y_min)
    print(f'  Plate: TL=({tl[0]:.0f}, {tl[1]:.0f})  TR=({tr[0]:.0f}, {tr[1]:.0f})')
    print(f'         BL=({bl[0]:.0f}, {bl[1]:.0f})  BR=({br[0]:.0f}, {br[1]:.0f})')
    print(f'  Size: {plate_w_px:.0f}×{plate_h_px:.0f} px  '
          f'(aspect {plate_w_px / plate_h_px:.3f}, expected {PLATE_W / PLATE_H:.3f})')

    hl_p, hr_p = detect_holes(gray_ref,
                                   {'tl': tl, 'tr': tr, 'bbox': bbox})

    if hl_p is None or hr_p is None:
        print('  Hole detection failed — using corners-only registration')
        src_pts = [tl, tr, bl, br]
        dst_pts = [np.array([0, 0]), np.array([GEN_W, 0]),
                   np.array([0, GEN_H]), np.array([GEN_W, GEN_H])]
    else:
        print(f'  Holes: L=({hl_p[0]:.0f}, {hl_p[1]:.0f})'
              f'  R=({hr_p[0]:.0f}, {hr_p[1]:.0f})')
        src_pts = [tl, tr, hl_p, hr_p]
        dst_pts = [np.array([0.0, 0.0]), np.array([float(GEN_W), 0.0]),
                   HOLE_L.copy(), HOLE_R.copy()]

    H_ref = homography_dlt(src_pts, dst_pts)
    warped_ref = warp(img_ref, H_ref, (GEN_H, GEN_W))
    warped_ref_gray = to_gray(warped_ref)

    print('  Outputs:')
    features_p = {'hole_L': hl_p, 'hole_R': hr_p,
                  'tl': tl, 'tr': tr, 'bl': bl, 'br': br, 'bbox': bbox}
    save_debug(img_ref, features_p, DIR / 'reference_debug.png',
               'reference — detected features', px_mm=plate_w_px / PLATE_W)
    Image.fromarray(warped_ref).save(DIR / 'reference_warped.png')
    print(f'  reference_warped.png')
    save_overlay(warped_ref, gen_rgba, DIR / 'reference_overlay.png')
    save_edges(warped_ref_gray, gen_gray, DIR / 'reference_edges.png')
    save_crops(warped_ref, gen_rgba, DIR / Path('reference'))

    print('\n  Measurements:')
    print_measurements('reference', hl_p, hr_p,
                       plate_w_px, plate_h_px, float(y_max),
                       warped_ref, warped_ref_gray)

    print('\nDone. Inspect output PNGs in scale/')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
