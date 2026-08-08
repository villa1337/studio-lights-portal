#!/usr/bin/env python3
"""Studio Lights Portal — localhost control panel for all room lights."""

import subprocess
import json
import os
from flask import Flask, send_from_directory, jsonify, request

app = Flask(__name__, static_folder="static")

# --- Config ---
HOST = "127.0.0.1"
PORT = 5337
RGB_COLOR_FILE = os.path.expanduser("~/.config/rgb/color")
NANOLEAF_CONFIG = os.path.expanduser("~/.config/nanoleaf/config")

# Light identifiers
HUE_LIGHTS = {
    "techoficina": "TechoOficina",
    "ofilamp": "e00a74d6-674e-445e-bcd5-ef4eec4dfd88",  # by ID (name lookup broken)
    "iris": "Iris",
}

# RAM i2c addresses
RAM_ADDRS = ["0x61", "0x63"]
I2C_BUS = "9"


def run_cmd(cmd, timeout=10):
    """Run a shell command and return (success, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "", "timeout"
    except Exception as e:
        return False, "", str(e)


def hex_to_rgb(hex_color):
    """Convert RRGGBB hex string to (r, g, b) tuple."""
    h = hex_color.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


# --- Routes ---


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/status")
def status():
    """Get current color from config file."""
    try:
        with open(RGB_COLOR_FILE, "r") as f:
            lines = f.read().strip().split("\n")
        primary = lines[0] if lines else "000000"
        secondary = lines[1] if len(lines) > 1 else primary
        return jsonify({"primary": primary, "secondary": secondary})
    except FileNotFoundError:
        return jsonify({"primary": "000000", "secondary": "000000"})


@app.route("/api/all", methods=["POST"])
def set_all():
    """Set ALL lights to one color (wraps rgb-set)."""
    data = request.get_json()
    color = data.get("color", "").lstrip("#")
    if not color or len(color) != 6:
        return jsonify({"error": "Invalid color"}), 400

    ok, out, err = run_cmd(f"rgb-set {color}", timeout=15)
    return jsonify({"success": ok, "output": out, "error": err})


@app.route("/api/all/off", methods=["POST"])
def all_off():
    """Turn off ALL lights (wraps rgb-set off)."""
    ok, out, err = run_cmd("rgb-set off", timeout=15)
    return jsonify({"success": ok, "output": out, "error": err})


@app.route("/api/hue/<light_id>", methods=["POST"])
def set_hue(light_id):
    """Set a specific Hue light."""
    data = request.get_json()
    color = data.get("color", "").lstrip("#")
    action = data.get("action", "on")  # "on" or "off"

    if light_id not in HUE_LIGHTS:
        return jsonify({"error": f"Unknown light: {light_id}"}), 400

    identifier = HUE_LIGHTS[light_id]

    if action == "off":
        cmd = f'openhue set light "{identifier}" --off'
    else:
        if not color or len(color) != 6:
            return jsonify({"error": "Invalid color"}), 400
        # Use --brightness for specific lights
        brightness = data.get("brightness", 100)
        cmd = f'openhue set light "{identifier}" --on --rgb "#{color}" --brightness {brightness}'

    ok, out, err = run_cmd(cmd)
    return jsonify({"success": ok, "output": out, "error": err})


@app.route("/api/nanoleaf", methods=["POST"])
def set_nanoleaf():
    """Set Nanoleaf panels."""
    data = request.get_json()
    colors = data.get("colors", [])  # list of hex colors (1-5)
    action = data.get("action", "on")

    if action == "off":
        # Set to black at brightness 0 (never truly off — firmware bug workaround)
        cmd = "nanoleaf-set 000000"
        ok, out, err = run_cmd(cmd)
        return jsonify({"success": ok, "output": out, "error": err})

    if not colors:
        return jsonify({"error": "No colors provided"}), 400

    # Clean hex values
    clean_colors = [c.lstrip("#") for c in colors[:5]]
    color_args = " ".join(clean_colors)
    cmd = f"nanoleaf-set {color_args}"

    ok, out, err = run_cmd(cmd)

    # Set brightness if specified
    brightness = data.get("brightness")
    if brightness is not None:
        # Read nanoleaf config for IP/token
        try:
            config = {}
            with open(NANOLEAF_CONFIG, "r") as f:
                for line in f:
                    if "=" in line:
                        k, v = line.strip().split("=", 1)
                        config[k.strip()] = v.strip()
            ip = config.get("NANOLEAF_IP", "192.168.0.198")
            port = config.get("NANOLEAF_PORT", "16021")
            token = config.get("NANOLEAF_TOKEN", "")
            bri_cmd = (
                f'curl -s -X PUT "http://{ip}:{port}/api/v1/{token}/state" '
                f'-d \'{{"brightness":{{"value":{brightness}}}}}\''
            )
            run_cmd(bri_cmd)
        except Exception:
            pass

    return jsonify({"success": ok, "output": out, "error": err})


@app.route("/api/rgb/ram", methods=["POST"])
def set_ram():
    """Set RAM RGB (both sticks via i2cset)."""
    data = request.get_json()
    color = data.get("color", "").lstrip("#")
    action = data.get("action", "on")

    if action == "off":
        # Set brightness to 0
        for addr in RAM_ADDRS:
            run_cmd(f"i2cset -y {I2C_BUS} {addr} 0x08 0x53")
            run_cmd(f"i2cset -y {I2C_BUS} {addr} 0x20 0x00")
            run_cmd(f"i2cset -y {I2C_BUS} {addr} 0x08 0x44")
        return jsonify({"success": True})

    if not color or len(color) != 6:
        return jsonify({"error": "Invalid color"}), 400

    r, g, b = hex_to_rgb(color)

    for addr in RAM_ADDRS:
        run_cmd(f"i2cset -y {I2C_BUS} {addr} 0x08 0x53")  # config mode
        run_cmd(f"i2cset -y {I2C_BUS} {addr} 0x09 0x00")  # static mode
        run_cmd(f"i2cset -y {I2C_BUS} {addr} 0x31 {hex(r)}")  # red
        run_cmd(f"i2cset -y {I2C_BUS} {addr} 0x32 {hex(g)}")  # green
        run_cmd(f"i2cset -y {I2C_BUS} {addr} 0x33 {hex(b)}")  # blue
        run_cmd(f"i2cset -y {I2C_BUS} {addr} 0x20 0x50")  # brightness 80%
        run_cmd(f"i2cset -y {I2C_BUS} {addr} 0x08 0x44")  # apply

    return jsonify({"success": True})


@app.route("/api/rgb/gpu", methods=["POST"])
def set_gpu():
    """Set GPU LED via OpenRGB."""
    data = request.get_json()
    color = data.get("color", "").lstrip("#")
    action = data.get("action", "on")

    if action == "off":
        color = "000000"

    if not color or len(color) != 6:
        return jsonify({"error": "Invalid color"}), 400

    cmd = f'openrgb --noautoconnect -d "RTX 5070" -m direct -c {color}'
    ok, out, err = run_cmd(cmd)
    return jsonify({"success": ok, "output": out, "error": err})


@app.route("/api/rgb/mobo", methods=["POST"])
def set_mobo():
    """Set motherboard + cooler LEDs via OpenRGB."""
    data = request.get_json()
    color = data.get("color", "").lstrip("#")
    action = data.get("action", "on")

    if action == "off":
        color = "000000"

    if not color or len(color) != 6:
        return jsonify({"error": "Invalid color"}), 400

    # Cooler = zones 0-1, Mobo accent = zones 2-3
    cmds = [
        f'openrgb --noautoconnect -d "B650 AORUS" -z 0 -m static -c {color} -sz 30',
        f'openrgb --noautoconnect -d "B650 AORUS" -z 1 -m static -c {color} -sz 30',
        f'openrgb --noautoconnect -d "B650 AORUS" -z 2 -m static -c {color}',
        f'openrgb --noautoconnect -d "B650 AORUS" -z 3 -m static -c {color}',
    ]

    results = []
    for cmd in cmds:
        ok, out, err = run_cmd(cmd)
        results.append(ok)

    return jsonify({"success": all(results)})


@app.route("/api/rgb/dual", methods=["POST"])
def set_dual():
    """Set dual-color mode (color1 → RAM+GPU, color2 → mobo+cooler). Wraps rgb-dual.sh."""
    data = request.get_json()
    color1 = data.get("color1", "").lstrip("#")
    color2 = data.get("color2", "").lstrip("#")

    if not color1 or len(color1) != 6 or not color2 or len(color2) != 6:
        return jsonify({"error": "Need two valid colors"}), 400

    cmd = f"rgb-dual.sh {color1} {color2}"
    ok, out, err = run_cmd(cmd, timeout=15)
    return jsonify({"success": ok, "output": out, "error": err})


@app.route("/api/mood/sync", methods=["POST"])
def mood_sync():
    """Trigger mood sync (extract colors from current wallpaper, sync all lights)."""
    ok, out, err = run_cmd("sync-lights.sh", timeout=30)
    return jsonify({"success": ok, "output": out, "error": err})


@app.route("/api/mood/new", methods=["POST"])
def mood_new():
    """Fetch new wallpaper + sync all lights."""
    ok, out, err = run_cmd("change-wallpaper.sh", timeout=45)
    return jsonify({"success": ok, "output": out, "error": err})


if __name__ == "__main__":
    print(f"🎨 Studio Lights Portal running at http://{HOST}:{PORT}")
    app.run(host=HOST, port=PORT, debug=False)
