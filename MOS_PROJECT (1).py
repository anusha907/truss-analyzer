import numpy as np
GRID_LIMIT = 10.0


# Stop function
class EmergencyStop(Exception):
    pass

# Input text helpers 

def header(title):                             # This is for the user to see the section of work
    print(f"  {title}")
    print("=" * 60)

def section(title):
    print(f"\n  >> {title}")

def prompt(msg, default=None):                                                       # All these prompt functions handle wrong inpus by the users.
    hint = f"  [{default}]" if default is not None else ""
    val = input(f"    {msg}{hint}: ").strip()
    if val.lower() == "stop":
        raise EmergencyStop()                                                        # If user enters stop the program comes to an end.
    if val == "" and default is not None:
        return str(default)
    return val

def prompt_float(msg, default=None):
    while True:
        val = prompt(msg, default)
        try:
            return float(val)
        except ValueError:
            print("    please enter a number")

def prompt_int(msg, default=None):
    while True:
        val = prompt(msg, default)
        try:
            return int(val)
        except ValueError:
            print("    please enter an integer")

def prompt_choice(msg, choices, default=None):
    lower = [c.lower() for c in choices]
    while True:
        val = prompt(f"{msg} ({'/'.join(choices)})", default)
        if val.lower() in lower:
            return val.lower()
        print(f"    choose one of: {', '.join(choices)}")

def yn(msg, default="y"):
    return prompt_choice(msg, ["y", "n"], default) == "y"


# GRID SCALING:

def fit_to_grid(joints):                                                                        # This part sets up the grid and scales the truss down if exceeding limits.
    all_coords = [c for xy in joints.values() for c in xy]
    if max(abs(c) for c in all_coords) <= GRID_LIMIT:
        return joints, 1.0

    factor = 10.0
    print(f"\n  some joints fall outside the grid (-{GRID_LIMIT} to {GRID_LIMIT}).")
    scaled = {jid: (x / factor, y / factor) for jid, (x, y) in joints.items()}

    while max(abs(c) for xy in scaled.values() for c in xy) > GRID_LIMIT:
        factor *= 10.0
        scaled = {jid: (x / factor, y / factor) for jid, (x, y) in joints.items()}

    print(f"  coordinates divided by {factor:.0f}x to fit the canvas.")
    print(f"  forces and reactions are still calculated on your original dimensions.")
    return scaled, factor


# INPUT:

def collect_joints():                                                                               # Interaction between program and user is maganed by this part.
    header("STEP 1 - INPUT THE JOINTS")
    print("""
  The canvas is a fixed 20x20 grid with x and y running from -10 to 10.
  Origin (0, 0) is at the centre.

  Place the LEFTMOST point of your truss at (0, 0).
  Other joints will be calculated relative to that.

  If any coordinate exceeds the grid bounds the whole truss
  will be scaled down by a factor of 10.
""")
    joints = {}
    labels = {}
    jid = 0
    alpha = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    while True:
        default_lbl = alpha[jid] if jid < len(alpha) else str(jid)
        section(f"Joint #{jid + 1}")
        lbl = prompt("Label", default_lbl)
        x = prompt_float("x (m)")
        y = prompt_float("y (m)")
        joints[jid] = (x, y)
        labels[jid] = lbl.upper()
        jid += 1
        if not yn("Add another joint?", "y"):
            break

    print(f"\n  {len(joints)} joint(s) defined.")
    return joints, labels


def collect_members(joints, labels):                                                          # Member Inputs
    header("STEP 2 - CONNECT JOINT TO INPUT MEMBERS")
    lbl_to_id = {v: k for k, v in labels.items()}
    joint_list = "  ".join(
        f"{labels[i]}({joints[i][0]:.2f},{joints[i][1]:.2f})" for i in joints
    )
    print(f"\n  Joints: {joint_list}")
    print("""
  Enter each member as two joint labels, e.g. "A B".
""")
    members = []

    while True:
        section(f"Member #{len(members) + 1}")
        raw = prompt("Joints (e.g. A B or A-B)")
        parts = raw.replace("-", " ").split()
        if len(parts) != 2:
            print("    enter exactly two labels")
            continue
        a, b = parts[0].upper(), parts[1].upper()
        if a not in lbl_to_id or b not in lbl_to_id:
            missing = [x for x in [a, b] if x not in lbl_to_id]
            print(f"    unknown label(s): {', '.join(missing)}")
            continue
        ia, ib = lbl_to_id[a], lbl_to_id[b]
        if ia == ib:
            print("    a member can't connect a joint to itself")
            continue
        dup = any(
            (m[0] == ia and m[1] == ib) or (m[0] == ib and m[1] == ia)
            for m in members
        )
        if dup:
            print(f"    member {a}-{b} already exists")
        else:
            members.append((ia, ib))
            print(f"    member {a}-{b} added")

        if not yn("Add another member?", "y"):
            break

    print(f"\n  {len(members)} member(s) defined.")
    return members


def collect_supports(joints, labels):                                                           # Support inputs
    header("STEP 3 - ENTER THE SUPPORTS")
    lbl_to_id = {v: k for k, v in labels.items()}
    print("""
  For a statically determinate truss you need exactly 3 reaction unknowns:
    pin    = fixes X and Y (counts as 2)
    roller = fixes direction perpendicular to its surface (counts as 1)

  Roller surface angle:
    0   = horizontal surface, pushes vertically
    90  = vertical surface, pushes horizontally
""")
    supports = {}

    while True:
        section(f"Support #{len(supports) + 1}")
        lbl = prompt("Joint label").upper()
        if lbl not in lbl_to_id:
            print(f"    unknown joint '{lbl}'")
            continue
        jid = lbl_to_id[lbl]
        if jid in supports:
            print(f"    joint {lbl} already has a support")
            continue

        stype = prompt_choice("Type", ["pin", "roller"])
        angle = 0.0
        if stype == "roller":
            angle = prompt_float("Surface angle (deg, 0=horizontal)", 0)

        supports[jid] = {"type": stype, "angle": float(angle)}
        rcount = sum(2 if s["type"] == "pin" else 1 for s in supports.values())
        print(f"    {stype} at {lbl}, total reaction unknowns: {rcount}")

        if rcount >= 3 and not yn("Add another support?", "n"):
            break
        elif rcount < 3:
            print(f"    need {3 - rcount} more reaction unknown(s)")
            if not yn("Continue adding supports?", "y"):
                break

    rcount = sum(2 if s["type"] == "pin" else 1 for s in supports.values())
    if rcount != 3:
        print(f"\n  warning: {rcount} reaction unknown(s) - truss may not be statically determinate")
    else:
        print(f"\n  {len(supports)} support(s), 3 reaction unknowns - looks good")
    return supports


def collect_loads(joints, labels):                                                      # Load Inputs
    header("STEP 4 - APPLIED LOADS")
    lbl_to_id = {v: k for k, v in labels.items()}
    print("""
  Enter each load as a magnitude and direction angle.
    magnitude  =  force in kN (always positive)
    angle      =  direction in degrees, measured from the +x axis, CCW positive
                   0   = rightward
                   90  = upward
                   180 = leftward
                   270 = downward  (or -90)

  e.g. a 50 kN downward load will have a magnitude=50, angle=270 or -90 degrees
""")
    loads = {}

    while True:
        section(f"Load #{len(loads) + 1}")
        lbl = prompt("Joint label").upper()
        if lbl not in lbl_to_id:
            print(f"    unknown joint '{lbl}'")
            continue
        jid = lbl_to_id[lbl]

        mag = prompt_float("Magnitude (kN)")
        ang = prompt_float("Angle (deg, 0=right, 90=up, 270=down)")
        fx = mag * np.cos(np.radians(ang))
        fy = mag * np.sin(np.radians(ang))

        if jid in loads:
            loads[jid] = (loads[jid][0] + fx, loads[jid][1] + fy)
            print(f"    load added to {lbl} (cumulative)")
        else:
            loads[jid] = (fx, fy)
            print(f"    load at {lbl}: {mag:.3f} kN at {ang:.1f} deg  "
                  f"-> Fx={fx:.3f} kN, Fy={fy:.3f} kN")

        if not yn("Add another load?", "y"):
            break

    print(f"\n  {len(loads)} loaded joint(s).")
    return loads


# REACTION FORCES SOLUTION

def compute_reactions(joints, members, supports, loads):                                
    unknowns = []
    for jid, sup in supports.items():
        if sup["type"] == "pin":
            unknowns.append((jid, 1.0, 0.0))
            unknowns.append((jid, 0.0, 1.0))
        else:
            theta = np.radians(sup["angle"])
            unknowns.append((jid, -np.sin(theta), np.cos(theta)))

    if len(unknowns) != 3:
        raise ValueError(f"Need exactly 3 reaction unknowns, got {len(unknowns)}.")

    total_fx = sum(fx for fx, fy in loads.values())
    total_fy = sum(fy for fx, fy in loads.values())

    pivot_jid = next(
        (jid for jid, s in supports.items() if s["type"] == "pin"),
        list(supports.keys())[0]
    )
    xp, yp = joints[pivot_jid]

    M_loads = sum(
        (joints[jid][0] - xp) * fy - (joints[jid][1] - yp) * fx
        for jid, (fx, fy) in loads.items()
    )

    A = np.zeros((3, 3))
    b = np.array([-total_fx, -total_fy, -M_loads])

    for col, (jid, ux, uy) in enumerate(unknowns):
        xj, yj = joints[jid]
        A[0, col] = ux
        A[1, col] = uy
        A[2, col] = (xj - xp) * uy - (yj - yp) * ux

    R_vals = np.linalg.solve(A, b)

    react = {jid: [0.0, 0.0] for jid in supports}
    for col, (jid, ux, uy) in enumerate(unknowns):
        react[jid][0] += R_vals[col] * ux
        react[jid][1] += R_vals[col] * uy

    return {jid: tuple(v) for jid, v in react.items()}


# METHOD OF JOINTS

def method_of_joints(joints, members, supports, loads, reactions):
    n_mem = len(members)

    # map each joint to its connected member indices
    joint_members = {jid: [] for jid in joints}
    for m_idx, (s, e) in enumerate(members):
        joint_members[s].append(m_idx)
        joint_members[e].append(m_idx)

    forces = {}
    solve_log = []

    def ext_force(jid):
        fx, fy = loads.get(jid, (0.0, 0.0))
        if jid in reactions:
            rx, ry = reactions[jid]
            fx += rx
            fy += ry
        return fx, fy

    def unit_away(jid, m_idx):
        s, e = members[m_idx]
        other = e if s == jid else s
        xj, yj = joints[jid]
        xo, yo = joints[other]
        L = np.hypot(xo - xj, yo - yj)
        if L < 1e-12:
            raise RuntimeError(f"Zero-length member between joints {s} and {e}.")
        return (xo - xj) / L, (yo - yj) / L

    def known_sum(jid):
        fx_k, fy_k = ext_force(jid)
        for m_idx in joint_members[jid]:
            if m_idx in forces:
                ux, uy = unit_away(jid, m_idx)
                fx_k += forces[m_idx] * ux
                fy_k += forces[m_idx] * uy
        return fx_k, fy_k

    def pick_next():
        best, best_n = None, 999
        for jid in joints:
            n_unk = sum(1 for m in joint_members[jid] if m not in forces)
            has_ext = jid in loads or jid in reactions
            priority = n_unk - (0.5 if has_ext else 0)
            if 0 < n_unk <= 2 and priority < best_n:
                best, best_n = jid, priority
        return best

    for _ in range(n_mem * 10):
        if len(forces) == n_mem:
            break
        jid = pick_next()
        if jid is None:
            break
        unk_ms = [m for m in joint_members[jid] if m not in forces]
        if len(unk_ms) > 2:
            continue

        fx_k, fy_k = known_sum(jid)

        if len(unk_ms) == 0:
            solve_log.append({"type": "verify", "joint": jid,
                               "residual_fx": fx_k, "residual_fy": fy_k})
            continue

        if len(unk_ms) == 1:
            m_idx = unk_ms[0]
            ux, uy = unit_away(jid, m_idx)
            if abs(ux) >= abs(uy) and abs(ux) > 1e-12:
                f = -fx_k / ux
            elif abs(uy) > 1e-12:
                f = -fy_k / uy
            else:
                f = 0.0
            forces[m_idx] = f
            solve_log.append({"type": "1-unk", "joint": jid, "solved": {m_idx: f}})

        else:
            m0, m1 = unk_ms
            ux0, uy0 = unit_away(jid, m0)
            ux1, uy1 = unit_away(jid, m1)
            A = np.array([[ux0, ux1], [uy0, uy1]])
            b_vec = np.array([-fx_k, -fy_k])
            det = A[0, 0] * A[1, 1] - A[0, 1] * A[1, 0]
            if abs(det) < 1e-10:
                continue
            sol = np.linalg.solve(A, b_vec)
            forces[m0], forces[m1] = sol[0], sol[1]
            solve_log.append({"type": "2-unk", "joint": jid,
                               "solved": {m0: sol[0], m1: sol[1]}})

    if len(forces) < n_mem:
        unsolved = [i for i in range(n_mem) if i not in forces]
        raise RuntimeError(
            f"Could not solve members {unsolved}. "
            "Check the truss is stable and statically determinate."
        )

    return np.array([forces[i] for i in range(n_mem)]), solve_log


def fmt(val):
    return f"{val:.3f} kN"

def fmt_abs(val):
    return f"{abs(val):.3f} kN"


# IMAGE GENERATION:
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

def draw_truss(joints, members, labels, supports, loads, reactions, forces, solve_log):
    import matplotlib.patheffects as pe

    GL = GRID_LIMIT

    all_x = [v[0] for v in joints.values()]
    all_y = [v[1] for v in joints.values()]
    truss_w = max(all_x) - min(all_x) or 1.0
    truss_h = max(all_y) - min(all_y) or 1.0
    truss_span = max(truss_w, truss_h)

    ARR = truss_span * 0.12
    ARR = max(ARR, 0.4)   
    PERP_OFF = truss_span * 0.055
    PERP_OFF = max(PERP_OFF, 0.22)
    SZ = truss_span * 0.045
    SZ = max(SZ, 0.18)

    fig_w = max(14, truss_w * 2.2)
    fig_h = max(9,  truss_h * 3.5 + 3)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("#f8f9fa")

    ax.grid(True, color="#dee2e6", linewidth=0.5, zorder=0, linestyle="--")
    ax.axhline(0, color="#adb5bd", linewidth=0.6, zorder=1)
    ax.axvline(0, color="#adb5bd", linewidth=0.6, zorder=1)

    for sp in ax.spines.values():
        sp.set_color("#adb5bd")
    ax.tick_params(colors="#495057", labelsize=8)
    ax.set_xlabel("x  (m)", fontsize=10, color="#343a40")
    ax.set_ylabel("y  (m)", fontsize=10, color="#343a40")
    ax.set_aspect("equal")

    pad_x = truss_w * 0.40
    pad_y = truss_h * 0.80
    ax.set_xlim(min(all_x) - pad_x, max(all_x) + pad_x)
    ax.set_ylim(min(all_y) - pad_y, max(all_y) + pad_y)

    max_abs = max(abs(f) for f in forces) if len(forces) else 1.0

    TENSION_DARK   = "#1565c0"   # dark blue
    TENSION_LIGHT  = "#90caf9"   # light blue
    COMPRESS_DARK  = "#b71c1c"   # dark red
    COMPRESS_LIGHT = "#ef9a9a"   # light red
    ZERO_COL       = "#757575"   # grey for near-zero

    def member_color(f):
        ratio = abs(f) / max_abs
        if abs(f) < max_abs * 0.01:
            return ZERO_COL, 1.5
        if f > 0:
            r = 0.3 + 0.7 * ratio
            col = tuple(TENSION_LIGHT_rgb[i] * (1 - r) + TENSION_DARK_rgb[i] * r for i in range(3))
            return col, 1.8 + ratio * 4.5
        else:
            r = 0.3 + 0.7 * ratio
            col = tuple(COMPRESS_LIGHT_rgb[i] * (1 - r) + COMPRESS_DARK_rgb[i] * r for i in range(3))
            return col, 1.8 + ratio * 4.5

    def hex2rgb(h):
        h = h.lstrip("#")
        return tuple(int(h[i:i+2], 16) / 255.0 for i in (0, 2, 4))

    TENSION_DARK_rgb   = hex2rgb(TENSION_DARK)
    TENSION_LIGHT_rgb  = hex2rgb(TENSION_LIGHT)
    COMPRESS_DARK_rgb  = hex2rgb(COMPRESS_DARK)
    COMPRESS_LIGHT_rgb = hex2rgb(COMPRESS_LIGHT)

    for idx, (s, e) in enumerate(members):
        x1, y1 = joints[s]
        x2, y2 = joints[e]
        f = forces[idx]
        col, lw = member_color(f)
        ax.plot([x1, x2], [y1, y2], color=col, linewidth=lw,
                solid_capstyle="round", zorder=2)

    cx_truss = np.mean(all_x)
    cy_truss = np.mean(all_y)

    for idx, (s, e) in enumerate(members):
        x1, y1 = joints[s]
        x2, y2 = joints[e]
        f = forces[idx]
        col, _ = member_color(f)

        mx, my = (x1 + x2) / 2, (y1 + y2) / 2  
        dx, dy = x2 - x1, y2 - y1
        L = np.hypot(dx, dy)

        px, py = -dy / L, dx / L

        to_cx = cx_truss - mx
        to_cy = cy_truss - my
        if px * to_cx + py * to_cy > 0:  
            px, py = -px, -py

        lx = mx + px * PERP_OFF
        ly = my + py * PERP_OFF

        nat = "T" if f >= 0 else "C"
        if abs(f) < max_abs * 0.01:
            nat = "0"
        label_str = f"{fmt_abs(f)}\n({nat})"

        ax.plot([mx, lx], [my, ly], color=col, lw=0.6,
                linestyle=":", zorder=5, alpha=0.7)

        ax.text(lx, ly, label_str,
                ha="center", va="center", fontsize=7.5,
                fontfamily="monospace", color=col,
                bbox=dict(boxstyle="round,pad=0.28",
                          fc="white", ec=col, lw=0.8, alpha=0.95),
                zorder=6)


    order_map = {step["joint"]: rank for rank, step in enumerate(solve_log)}
    order_cmap = plt.cm.tab10
    n_joints = len(joints)

    for jid, (x, y) in joints.items():
        rank = order_map.get(jid, -1)
        jcol = order_cmap(rank % 10 / 10.0) if rank >= 0 else "#555555"

        ax.plot(x, y, "o", markersize=12, color="white",
                markeredgecolor=jcol, markeredgewidth=2.2, zorder=7)
        ax.plot(x, y, ".", markersize=4, color=jcol, zorder=8)

        lbl = labels.get(jid, str(jid))
        badge = f"({rank + 1})" if rank >= 0 else ""

        ax.text(x, y + SZ * 1.8, f"{lbl}{badge}",
                ha="center", va="bottom", fontsize=9,
                fontweight="bold", color="#212529",
                fontfamily="monospace", zorder=9,
                bbox=dict(boxstyle="round,pad=0.15",
                          fc="white", ec="#ced4da", lw=0.5, alpha=0.9))


    for jid, sup in supports.items():
        x, y = joints[jid]
        angle = sup.get("angle", 0.0)
        theta = np.radians(angle)

        nx, ny = np.sin(theta), -np.cos(theta)
        tx, ty = np.cos(theta),  np.sin(theta)

        base_x = x + nx * 2.2 * SZ
        base_y = y + ny * 2.2 * SZ

        tri = plt.Polygon(
            [[x, y],
             [base_x - tx * SZ, base_y - ty * SZ],
             [base_x + tx * SZ, base_y + ty * SZ]],
            closed=True,
            facecolor="#fff3b0", edgecolor="#e09000", lw=1.8, zorder=10
        )
        ax.add_patch(tri)

        if sup["type"] == "pin":
            # hatching lines below base
            for k in range(7):
                bx = base_x + tx * (-SZ * 1.4 + k * SZ * 0.47)
                by = base_y + ty * (-SZ * 1.4 + k * SZ * 0.47)
                ax.plot([bx, bx + nx * SZ * 0.55],
                        [by, by + ny * SZ * 0.55],
                        color="#e09000", lw=1.0, zorder=10)
            ax.plot([base_x - tx * SZ * 1.4, base_x + tx * SZ * 1.4],
                    [base_y - ty * SZ * 1.4, base_y + ty * SZ * 1.4],
                    color="#e09000", lw=1.5, zorder=10)
        else:
            # roller circles
            for sign in (-0.55, 0.55):
                cx_ = base_x + tx * sign * SZ
                cy_ = base_y + ty * sign * SZ
                circ = plt.Circle(
                    (cx_ + nx * SZ * 0.35, cy_ + ny * SZ * 0.35),
                    SZ * 0.28,
                    facecolor="white", edgecolor="#e09000", lw=1.5, zorder=10
                )
                ax.add_patch(circ)
            ax.plot([base_x - tx * SZ * 1.4, base_x + tx * SZ * 1.4],
                    [base_y - ty * SZ * 1.4, base_y + ty * SZ * 1.4],
                    color="#e09000", lw=1.5, zorder=10)

    if loads:
        max_load = max(np.hypot(fx, fy) for fx, fy in loads.values()) or 1.0
        for jid, (fx, fy) in loads.items():
            if abs(fx) + abs(fy) < 1e-9:
                continue
            x, y = joints[jid]
            mag = np.hypot(fx, fy)
            ux, uy = fx / mag, fy / mag
            al = ARR * (0.6 + 0.4 * mag / max_load)

            tail_x, tail_y = x - ux * al, y - uy * al

            ax.annotate("",
                xy=(x, y),                        
                xytext=(tail_x, tail_y),           
                arrowprops=dict(
                    arrowstyle="-|>",
                    color="#d4500a",
                    lw=2.2,
                    mutation_scale=16
                ), zorder=11)

            lx = tail_x - ux * PERP_OFF * 0.6
            ly = tail_y - uy * PERP_OFF * 0.6
            ax.text(lx, ly, fmt_abs(mag),
                    ha="center", va="center", fontsize=8,
                    fontweight="bold", color="#d4500a",
                    fontfamily="monospace",
                    bbox=dict(boxstyle="round,pad=0.25",
                              fc="white", ec="#d4500a", lw=0.8, alpha=0.95),
                    zorder=12)

    
    for jid, (rx_val, ry_val) in reactions.items():
        x, y = joints[jid]

        for val, (ux2, uy2) in [(rx_val, (1.0, 0.0)), (ry_val, (0.0, 1.0))]:
            if abs(val) < 1e-6:
                continue
            sign = np.sign(val)
            head_x = x + ux2 * sign * ARR * 0.85
            head_y = y + uy2 * sign * ARR * 0.85

            ax.annotate("",
                xy=(head_x, head_y),             
                xytext=(x, y),                    
                arrowprops=dict(
                    arrowstyle="-|>",
                    color="#1a7a40",
                    lw=2.0,
                    mutation_scale=14
                ), zorder=11)

        parts = []
        if abs(rx_val) > 0.001:
            parts.append(f"Rx = {fmt(rx_val)}")
        if abs(ry_val) > 0.001:
            parts.append(f"Ry = {fmt(ry_val)}")
        if parts:
            ax.text(x, y - SZ * 6.5, "\n".join(parts),
                    ha="center", va="top", fontsize=8,
                    color="#1a7a40", fontfamily="monospace",
                    bbox=dict(boxstyle="round,pad=0.3",
                              fc="white", ec="#1a7a40", lw=0.8, alpha=0.95),
                    zorder=12)

    t_patch  = mpatches.Patch(facecolor=TENSION_DARK,   edgecolor="none", label="Tension  (+)")
    c_patch  = mpatches.Patch(facecolor=COMPRESS_DARK,  edgecolor="none", label="Compression  (−)")
    s_patch  = mpatches.Patch(facecolor="#fff3b0",      edgecolor="#e09000", label="Support")
    l_patch  = mpatches.Patch(facecolor="#d4500a",      edgecolor="none", label="Applied Load")
    r_patch  = mpatches.Patch(facecolor="#1a7a40",      edgecolor="none", label="Reaction")
    o_patch  = mpatches.Patch(facecolor="#888888",      edgecolor="none", label="Joint solve order")

    leg = ax.legend(handles=[t_patch, c_patch, s_patch, l_patch, r_patch, o_patch],
                    loc="upper right", framealpha=0.95,
                    facecolor="white", edgecolor="#adb5bd",
                    labelcolor="#212529", fontsize=8.5,
                    title="Legend", title_fontsize=9.5)
    leg.get_title().set_color("#343a40")
    leg.get_title().set_fontweight("bold")

    ax.set_title("2D Truss Analysis  —  Method of Joints  (ΣFx = 0,  ΣFy = 0  at every joint)",
                 fontsize=12, color="#212529", pad=14,
                 fontfamily="monospace", fontweight="bold")

    plt.tight_layout(pad=1.5)
    return fig


# PRINTED RESULT

def print_report(joints, members, labels, loads, reactions, forces, solve_log):
    W = 68
    print("\n" + "=" * W)
    print("  2D TRUSS  -  METHOD OF JOINTS".center(W))
    print("=" * W)

    print("\n  REACTIONS")
    print("  " + "-" * 50)
    for jid, (rx, ry) in reactions.items():
        lbl = labels.get(jid, jid)
        print(f"    Joint {lbl}:  Rx = {fmt(rx):>12},  Ry = {fmt(ry):>12}")

    print(f"\n{'=' * W}")
    print("  MEMBER FORCES")
    print(f"{'-' * W}")
    print(f"  {'#':>3}  {'Member':^10}  {'L (m)':>8}  {'Force (kN)':>14}  {'Nature':^13}")
    print(f"{'-' * W}")
    for idx, (s, e) in enumerate(members):
        xs_, ys_ = joints[s]
        xe, ye = joints[e]
        L = np.hypot(xe - xs_, ye - ys_)
        f = forces[idx]
        ml = f"{labels.get(s, s)}-{labels.get(e, e)}"
        nat = "TENSION" if f >= 0 else "COMPRESSION"
        print(f"  {idx:>3}  {ml:^10}  {L:>8.3f}  {fmt(f):>14}  {nat:^13}")
    print("=" * W + "\n")


def load_preset():
    joints = {
        0: (0.0, 0.0), 1: (2.0, 0.0), 2: (4.0, 0.0),
        3: (6.0, 0.0), 4: (8.0, 0.0),
        5: (1.0, 2.0), 6: (3.0, 2.0), 7: (5.0, 2.0), 8: (7.0, 2.0),
    }
    labels = {0: "A", 1: "B", 2: "C", 3: "D", 4: "E",
              5: "F", 6: "G", 7: "H", 8: "I"}
    members = [
        (0, 1), (1, 2), (2, 3), (3, 4),
        (5, 6), (6, 7), (7, 8),
        (0, 5), (1, 5), (1, 6), (2, 6), (2, 7), (3, 7), (3, 8), (4, 8),
    ]
    supports = {
        0: {"type": "pin",    "angle": 0.0},
        4: {"type": "roller", "angle": 0.0},
    }
    # loads as (Fx, Fy) in kN
    loads = {1: (0.0, -50.0), 2: (0.0, -80.0), 3: (0.0, -50.0)}
    return joints, labels, members, supports, loads


def main():
    print("""
  2D TRUSS ANALYZER: Method of Joints

  Canvas: 20x20 grid, x and y from -10 to 10, origin at centre.
  Place the leftmost joint of your truss at (0, 0).
""")
    use_preset = yn("See the example truss? (n to enter your own)", "y")

    try:
        if use_preset:
            joints, labels, members, supports, loads = load_preset()
            print("\n  Truss loaded")
        else:
            joints, labels = collect_joints()
            # scale down to fit grid if needed
            joints, scale_factor = fit_to_grid(joints)
            if scale_factor > 1.0:
                print(f"\n  note: coordinates were scaled for display only. "
                      "forces are calculated on your original dimensions.")
            members = collect_members(joints, labels)
            supports = collect_supports(joints, labels)
            loads = collect_loads(joints, labels)

    except EmergencyStop:
        print("\n\n  !! Program ended.\n")
        return

    print("\n  computing reactions...")
    try:
        reactions = compute_reactions(joints, members, supports, loads)
    except Exception as e:
        print(f"\n  reaction solver failed: {e}")
        return

    print("  solving member forces...")
    try:
        forces, solve_log = method_of_joints(joints, members, supports, loads, reactions)
    except Exception as e:
        print(f"\n  member-force solver failed: {e}")
        return

    print("  done\n")

    print_report(joints, members, labels, loads, reactions, forces, solve_log)

    print("  generating figure...")
    fig = draw_truss(joints, members, labels, supports, loads,
                     reactions, forces, solve_log)

    out = "truss_analysis_output.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"  saved -> {out}\n")
    plt.show()


if __name__ == "__main__":
    main() 